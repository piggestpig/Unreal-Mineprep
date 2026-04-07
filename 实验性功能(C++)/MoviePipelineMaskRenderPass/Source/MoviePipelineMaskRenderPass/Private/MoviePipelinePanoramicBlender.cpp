// Copyright Epic Games, Inc. All Rights Reserved.
#include "MoviePipelinePanoramicBlender.h"
#include "Math/PerspectiveMatrix.h"
#include "MoviePipelinePanoramicPass.h"
#include "ImagePixelData.h"

namespace UE::MoviePipeline
{
FMoviePipelinePanoramicBlender::FMoviePipelinePanoramicBlender(TSharedPtr<::MoviePipeline::IMoviePipelineOutputMerger> InOutputMerger, const FIntPoint InOutputResolution, bool bInStereo, EStereoOutputFormat InStereoOutputFormat, bool bInDisablePanoramic)
	: OutputMerger(InOutputMerger)
	, bStereo(bInStereo)
	, StereoOutputFormat(InStereoOutputFormat)
	, bDisablePanoramic(bInDisablePanoramic)
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
			
			if (!bDisablePanoramic)
			{
				TargetBlender->Blender.Initialize(OutputResolution);
			}
		}
	}

	// Handle bDisablePanoramic mode: store raw pixels directly without panoramic blending
	if (bDisablePanoramic)
	{
		// For non-panoramic stereo, copy the pixel data
		// Use CopyImageData to get a copy we can convert safely
		TUniquePtr<FImagePixelData> CopiedData = InData->CopyImageData();
		
		FScopeLock ScopeLock(&GlobalQueueDataMutex);
		const FIntPoint Size = CopiedData->GetSize();
		TargetBlender->RawPixels.SetNumUninitialized(Size.X * Size.Y);
		
		// Convert to FLinearColor based on the actual pixel type
		if (CopiedData->GetType() == EImagePixelType::Float32)
		{
			const TImagePixelData<FLinearColor>* LinearColorData = static_cast<const TImagePixelData<FLinearColor>*>(CopiedData.Get());
			TargetBlender->RawPixels = LinearColorData->Pixels;
		}
		else if (CopiedData->GetType() == EImagePixelType::Float16)
		{
			const TImagePixelData<FFloat16Color>* Float16Data = static_cast<const TImagePixelData<FFloat16Color>*>(CopiedData.Get());
			for (int64 i = 0; i < Float16Data->Pixels.Num(); ++i)
			{
				TargetBlender->RawPixels[i] = FLinearColor(Float16Data->Pixels[i]);
			}
		}
		else if (CopiedData->GetType() == EImagePixelType::Color)
		{
			const TImagePixelData<FColor>* ColorData = static_cast<const TImagePixelData<FColor>*>(CopiedData.Get());
			for (int64 i = 0; i < ColorData->Pixels.Num(); ++i)
			{
				TargetBlender->RawPixels[i] = FLinearColor(ColorData->Pixels[i]);
			}
		}
	}
	else
	{
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
	}

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
		
		if (!bDisablePanoramic)
		{
			TargetBlender->Blender.TaskConcurrencyLimiter->Wait();
			if (bIsStereo && OtherEyeBlender)
			{
				OtherEyeBlender->Blender.TaskConcurrencyLimiter->Wait();
			}
		}
		
		if (ensure(OutputMerger.IsValid()))
		{
			int32 OutputSizeX = OutputResolution.X;
			int32 OutputSizeY = OutputResolution.Y;
			
			if (bIsStereo && OtherEyeBlender)
			{
				// Get left and right eye pixels
				TArray64<FLinearColor> LeftPixels, RightPixels;
				if (bDisablePanoramic)
				{
					// For non-panoramic mode, use raw pixels directly
					if (TargetBlender->EyeIndex == 0)
					{
						LeftPixels = MoveTemp(TargetBlender->RawPixels);
						RightPixels = MoveTemp(OtherEyeBlender->RawPixels);
					}
					else
					{
						RightPixels = MoveTemp(TargetBlender->RawPixels);
						LeftPixels = MoveTemp(OtherEyeBlender->RawPixels);
					}
				}
				else
				{
					// For panoramic mode, fetch from blender
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
				}
				
				// Output based on StereoOutputFormat
				switch (StereoOutputFormat)
				{
				case EStereoOutputFormat::Separate:
					{
						// Output left eye
						TSharedRef<FPanoramicImagePixelDataPayload> LeftPayload = StaticCastSharedRef<FPanoramicImagePixelDataPayload>(DataPayload->Copy());
						LeftPayload->PassIdentifier = FMoviePipelinePassIdentifier(TEXT("nDisplayLit_L"));
						TUniquePtr<TImagePixelData<FLinearColor>> LeftPixelData = MakeUnique<TImagePixelData<FLinearColor>>(FIntPoint(OutputSizeX, OutputSizeY), MoveTemp(LeftPixels), LeftPayload);
						OutputMerger.Pin()->OnCompleteRenderPassDataAvailable_AnyThread(MoveTemp(LeftPixelData));
						
						// Output right eye
						TSharedRef<FPanoramicImagePixelDataPayload> RightPayload = StaticCastSharedRef<FPanoramicImagePixelDataPayload>(DataPayload->Copy());
						RightPayload->PassIdentifier = FMoviePipelinePassIdentifier(TEXT("nDisplayLit_R"));
						TUniquePtr<TImagePixelData<FLinearColor>> RightPixelData = MakeUnique<TImagePixelData<FLinearColor>>(FIntPoint(OutputSizeX, OutputSizeY), MoveTemp(RightPixels), RightPayload);
						OutputMerger.Pin()->OnCompleteRenderPassDataAvailable_AnyThread(MoveTemp(RightPixelData));
					}
					break;
					
				case EStereoOutputFormat::SideBySide:
					{
						// Combine left and right side by side (width x 2)
						TArray64<FLinearColor> CombinedPixels;
						CombinedPixels.SetNumUninitialized(OutputSizeX * 2 * OutputSizeY);
						
						for (int32 Y = 0; Y < OutputSizeY; ++Y)
						{
							// Left eye on the left side
							FMemory::Memcpy(
								&CombinedPixels[Y * OutputSizeX * 2],
								&LeftPixels[Y * OutputSizeX],
								OutputSizeX * sizeof(FLinearColor));
							// Right eye on the right side
							FMemory::Memcpy(
								&CombinedPixels[Y * OutputSizeX * 2 + OutputSizeX],
								&RightPixels[Y * OutputSizeX],
								OutputSizeX * sizeof(FLinearColor));
						}
						
						TSharedRef<FPanoramicImagePixelDataPayload> CombinedPayload = StaticCastSharedRef<FPanoramicImagePixelDataPayload>(DataPayload->Copy());
						TUniquePtr<TImagePixelData<FLinearColor>> CombinedPixelData = MakeUnique<TImagePixelData<FLinearColor>>(
							FIntPoint(OutputSizeX * 2, OutputSizeY), MoveTemp(CombinedPixels), CombinedPayload);
						OutputMerger.Pin()->OnCompleteRenderPassDataAvailable_AnyThread(MoveTemp(CombinedPixelData));
					}
					break;
					
				case EStereoOutputFormat::TopBottom:
					{
						// Combine left on top and right on bottom (height x 2)
						TArray64<FLinearColor> CombinedPixels;
						CombinedPixels.SetNumUninitialized(OutputSizeX * OutputSizeY * 2);
						
						// Left eye on top
						FMemory::Memcpy(
							CombinedPixels.GetData(),
							LeftPixels.GetData(),
							OutputSizeX * OutputSizeY * sizeof(FLinearColor));
						// Right eye on bottom
						FMemory::Memcpy(
							&CombinedPixels[OutputSizeX * OutputSizeY],
							RightPixels.GetData(),
							OutputSizeX * OutputSizeY * sizeof(FLinearColor));
						
						TSharedRef<FPanoramicImagePixelDataPayload> CombinedPayload = StaticCastSharedRef<FPanoramicImagePixelDataPayload>(DataPayload->Copy());
						TUniquePtr<TImagePixelData<FLinearColor>> CombinedPixelData = MakeUnique<TImagePixelData<FLinearColor>>(
							FIntPoint(OutputSizeX, OutputSizeY * 2), MoveTemp(CombinedPixels), CombinedPayload);
						OutputMerger.Pin()->OnCompleteRenderPassDataAvailable_AnyThread(MoveTemp(CombinedPixelData));
					}
					break;
					
				case EStereoOutputFormat::Anaglyph:
					{
						// Red-Cyan anaglyph: Red channel from left eye, Green+Blue from right eye
						TArray64<FLinearColor> AnaglyphPixels;
						AnaglyphPixels.SetNumUninitialized(OutputSizeX * OutputSizeY);
						
						for (int64 i = 0; i < OutputSizeX * OutputSizeY; ++i)
						{
							// Left eye luminance for red channel
							float LeftLuminance = 0.299f * LeftPixels[i].R + 0.587f * LeftPixels[i].G + 0.114f * LeftPixels[i].B;
							// Right eye for cyan (green + blue)
							AnaglyphPixels[i] = FLinearColor(
								LeftLuminance,
								RightPixels[i].G,
								RightPixels[i].B,
								FMath::Max(LeftPixels[i].A, RightPixels[i].A));
						}
						
						TSharedRef<FPanoramicImagePixelDataPayload> AnaglyphPayload = StaticCastSharedRef<FPanoramicImagePixelDataPayload>(DataPayload->Copy());
						TUniquePtr<TImagePixelData<FLinearColor>> AnaglyphPixelData = MakeUnique<TImagePixelData<FLinearColor>>(
							FIntPoint(OutputSizeX, OutputSizeY), MoveTemp(AnaglyphPixels), AnaglyphPayload);
						OutputMerger.Pin()->OnCompleteRenderPassDataAvailable_AnyThread(MoveTemp(AnaglyphPixelData));
					}
					break;
				}
			}
			else
			{
				// Non-stereo: output single image
				TArray64<FLinearColor> OutPixels;
				TargetBlender->Blender.FetchFinalPixelDataLinearColor(OutPixels);
				TUniquePtr<TImagePixelData<FLinearColor>> FinalPixelData = MakeUnique<TImagePixelData<FLinearColor>>(FIntPoint(OutputSizeX, OutputSizeY), MoveTemp(OutPixels), DataPayload->Copy());
				OutputMerger.Pin()->OnCompleteRenderPassDataAvailable_AnyThread(MoveTemp(FinalPixelData));
			}
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
