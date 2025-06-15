// Copyright Epic Games, Inc. All Rights Reserved.
#include "MoviePipelinePanoramicBlender.h"
#include "Math/PerspectiveMatrix.h"
#include "MoviePipelinePanoramicPass.h"

namespace UE::MoviePipeline
{
FMoviePipelinePanoramicBlender::FMoviePipelinePanoramicBlender(TSharedPtr<::MoviePipeline::IMoviePipelineOutputMerger> InOutputMerger, const FIntPoint InOutputResolution)
	: OutputMerger(InOutputMerger)
{
	OutputResolution = InOutputResolution;
}

DECLARE_CYCLE_STAT(TEXT("STAT_MoviePipeline_PanoBlendWait"), STAT_MoviePipeline_PanoBlendWait, STATGROUP_MoviePipeline);

void FMoviePipelinePanoramicBlender::OnCompleteRenderPassDataAvailable_AnyThread(TUniquePtr<FImagePixelData>&& InData)
{
	// Copy the payload at the start, because it will get destroyed when the pixel data is moved to a task, which then
	// uses it and discards it before this function finishes.
	TSharedRef<FPanoramicImagePixelDataPayload> DataPayload = StaticCastSharedRef<FPanoramicImagePixelDataPayload>(InData->GetPayload<FPanoramicImagePixelDataPayload>()->Copy());

	const int32 ThisEyeIndex = DataPayload->Pane.Data.EyeIndex;
	const int32 OutputFrameNumber = DataPayload->SampleState.OutputState.OutputFrameNumber;

	FPoolEntry* TargetBlender = nullptr;
	FPoolEntry* OtherEyeBlender = nullptr;
	{
		FScopeLock ScopeLock(&GlobalQueueDataMutex);

		// 查找当前眼的Blender
		for (TUniquePtr<FPoolEntry>& Item : PendingData)
		{
			if (Item->OutputFrameNumber == OutputFrameNumber && Item->EyeIndex == ThisEyeIndex && Item->bActive)
			{
				TargetBlender = Item.Get();
				break;
			}
		}

		if (!TargetBlender)
		{
			// 查找未激活的Blender复用
			for (TUniquePtr<FPoolEntry>& Item : PendingData)
			{
				if (!Item->bActive)
				{
					TargetBlender = Item.Get();
					break;
				}
			}
			if (!TargetBlender)
			{
				TUniquePtr<FPoolEntry> NewEntry = MakeUnique<FPoolEntry>();
				int32 NewIndex = PendingData.Add(MoveTemp(NewEntry));
				TargetBlender = PendingData[NewIndex].Get();
			}
			check(TargetBlender);
			TargetBlender->OutputFrameNumber = OutputFrameNumber;
			TargetBlender->EyeIndex = ThisEyeIndex;
			TargetBlender->bActive = true;
			TargetBlender->NumCompletedAccumulations = 0;
			TargetBlender->Blender.Initialize(OutputResolution);
		}
	}

	// This can get called later (due to blending being async) so only capture by value.
	auto OnDebugSampleAvailable = [
		DataPayloadCopy = DataPayload->Copy(),
		WeakOutputMerger = OutputMerger](FLinearColor* Data, FIntPoint Resolution)
		{
			TSharedRef<FPanoramicImagePixelDataPayload> PayloadAsPano = StaticCastSharedRef<FPanoramicImagePixelDataPayload>(DataPayloadCopy);
			if (!PayloadAsPano->SampleState.bWriteSampleToDisk)
			{
				return;
			}
			if (PayloadAsPano->Pane.Data.EyeIndex >= 0)
			{
				PayloadAsPano->Debug_OverrideFilename = FString::Printf(TEXT("/%s_PaneX_%d_PaneY_%dEye_%d-Blended.%d"),
					*PayloadAsPano->PassIdentifier.Name, PayloadAsPano->Pane.Data.HorizontalStepIndex,
					PayloadAsPano->Pane.Data.VerticalStepIndex, PayloadAsPano->Pane.Data.EyeIndex, PayloadAsPano->SampleState.OutputState.OutputFrameNumber);
			}
			else
			{
				PayloadAsPano->Debug_OverrideFilename = FString::Printf(TEXT("/%s_PaneX_%d_PaneY_%d-Blended.%d"),
					*PayloadAsPano->PassIdentifier.Name, PayloadAsPano->Pane.Data.HorizontalStepIndex,
					PayloadAsPano->Pane.Data.VerticalStepIndex, PayloadAsPano->SampleState.OutputState.OutputFrameNumber);
			}

			// We have to copy the memory because the blender is going to re-use it.
			TArray64<FLinearColor> BlendDataCopy = TArray64<FLinearColor>(Data, Resolution.X * Resolution.Y);
			TUniquePtr<TImagePixelData<FLinearColor>> FinalPixelData = MakeUnique<TImagePixelData<FLinearColor>>(Resolution, MoveTemp(BlendDataCopy), PayloadAsPano->Copy());

			if (ensure(WeakOutputMerger.IsValid()))
			{
				WeakOutputMerger.Pin()->OnSingleSampleDataAvailable_AnyThread(MoveTemp(FinalPixelData));
			}
		};

	// Now that we know which blender we're trying to accumulate to, we can just send the data to it directly. We're already
	// on a task thread, and the blending process supports multiple task threads working on blending at the same time.
	TargetBlender->Blender.BlendSample_AnyThread(MoveTemp(InData), DataPayload->Pane.Data, OnDebugSampleAvailable);

	bool bIsStereo = (ThisEyeIndex >= 0);
	bool bIsLastSample = false;
	{
		FScopeLock ScopeLock(&GlobalQueueDataMutex);
		TargetBlender->NumCompletedAccumulations++;

		int32 NumCompletedAccumulations = TargetBlender->NumCompletedAccumulations;
		const int32 ExpectedSamples = DataPayload->Pane.Data.NumHorizontalSteps * DataPayload->Pane.Data.NumVerticalSteps;
		const bool bLastSampleThisEye = (NumCompletedAccumulations == ExpectedSamples);

		if (bLastSampleThisEye)
		{
			// 查找另一只眼的Blender
			if (bIsStereo)
			{
				const int32 OtherEyeIndex = (ThisEyeIndex == 0) ? 1 : 0;
				for (TUniquePtr<FPoolEntry>& Item : PendingData)
				{
					if (Item->OutputFrameNumber == OutputFrameNumber && Item->EyeIndex == OtherEyeIndex && Item->bActive)
					{
						OtherEyeBlender = Item.Get();
						break;
					}
				}
				// 另一只眼也完成了才输出
				if (OtherEyeBlender && OtherEyeBlender->NumCompletedAccumulations == ExpectedSamples)
				{
					bIsLastSample = true;
				}
			}
			else
			{
				bIsLastSample = true;
			}
		}
	}

	if (bIsLastSample)
	{
		SCOPE_CYCLE_COUNTER(STAT_MoviePipeline_PanoBlendWait);
		TargetBlender->Blender.TaskConcurrencyLimiter->Wait();
		if (bIsStereo && OtherEyeBlender)
		{
			OtherEyeBlender->Blender.TaskConcurrencyLimiter->Wait();
		}
		if (ensure(OutputMerger.IsValid()))
		{
			int32 OutputSizeX = OutputResolution.X;
			int32 OutputSizeY = bIsStereo ? OutputResolution.Y * 2 : OutputResolution.Y;
			TUniquePtr<TImagePixelData<FLinearColor>> FinalPixelData = MakeUnique<TImagePixelData<FLinearColor>>(FIntPoint(OutputSizeX, OutputSizeY), DataPayload->Copy());
			TArray64<FLinearColor>& OutPixels = FinalPixelData->Pixels;
			OutPixels.SetNumZeroed(OutputSizeX * OutputSizeY);

			if (bIsStereo && OtherEyeBlender)
			{
				// 左右眼分别写入上下两半
				TArray64<FLinearColor> LeftPixels, RightPixels;
				if (TargetBlender->EyeIndex == 0)
				{
					TargetBlender->Blender.FetchFinalPixelDataLinearColor(LeftPixels);
					OtherEyeBlender->Blender.FetchFinalPixelDataLinearColor(RightPixels);
				}
				else
				{
					TargetBlender->Blender.FetchFinalPixelDataLinearColor(RightPixels);
					OtherEyeBlender->Blender.FetchFinalPixelDataLinearColor(LeftPixels);
				}
				int32 SingleEyeNum = OutputResolution.X * OutputResolution.Y;
				if (LeftPixels.Num() == SingleEyeNum && RightPixels.Num() == SingleEyeNum)
				{
					for (int32 i = 0; i < SingleEyeNum; ++i)
					{
						OutPixels[i] = LeftPixels[i];
						OutPixels[SingleEyeNum + i] = RightPixels[i];
					}
				}
			}
			else
			{
				TargetBlender->Blender.FetchFinalPixelDataLinearColor(OutPixels);
			}

			OutputMerger.Pin()->OnCompleteRenderPassDataAvailable_AnyThread(MoveTemp(FinalPixelData));
		}

		// 释放两个Blender
		TargetBlender->bActive = false;
		if (OtherEyeBlender)
			OtherEyeBlender->bActive = false;
	}
}

void FMoviePipelinePanoramicBlender::OnSingleSampleDataAvailable_AnyThread(TUniquePtr<FImagePixelData>&& InData)
{
	// This is used for debug output, just pass it straight through.
	ensure(OutputMerger.IsValid());
	OutputMerger.Pin()->OnSingleSampleDataAvailable_AnyThread(MoveTemp(InData));
}

static FMoviePipelineMergerOutputFrame MoviePipelineDummyOutputFrame;

FMoviePipelineMergerOutputFrame& FMoviePipelinePanoramicBlender::QueueOutputFrame_GameThread(const FMoviePipelineFrameOutputState& CachedOutputState)
{
	// Unsupported, the main Output Builder should be the one tracking this.
	check(0);
	return MoviePipelineDummyOutputFrame;
}

void FMoviePipelinePanoramicBlender::AbandonOutstandingWork()
{
	// Not yet implemented
	check(0);
}

int32 FMoviePipelinePanoramicBlender::GetNumOutstandingFrames() const
{
	return 0;
}

} // UE::MoviePipeline
