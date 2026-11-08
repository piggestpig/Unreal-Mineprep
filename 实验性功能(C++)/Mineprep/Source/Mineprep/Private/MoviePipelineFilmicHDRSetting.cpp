#include "MoviePipelineFilmicHDRSetting.h"

#include "MineprepDisplayHDRRenderTarget.h"
#include "Engine/Scene.h"
#include "MoviePipeline.h"
#include "MoviePipelineConsoleVariableSetting.h"
#include "MovieRenderPipelineDataTypes.h"
#include "RenderingThread.h"
#include "SceneView.h"

DEFINE_LOG_CATEGORY_STATIC(LogMineprepDisplayHDR, Log, All);

UMoviePipelineFilmicHDRSetting::UMoviePipelineFilmicHDRSetting() = default;
UMoviePipelineFilmicHDRSetting::~UMoviePipelineFilmicHDRSetting() = default;

bool UMoviePipelineFilmicHDRSetting::ValidateConfiguration(FString& OutError) const
{
    OutError.Reset();
    if (!FMath::IsFinite(PeakNits) || PeakNits <= 100.f || PeakNits > 10000.f)
    {
        OutError = TEXT("Filmic HDR peak must be finite, above 100 nits and at most 10000 nits.");
        return false;
    }
    if (!FMath::IsFinite(PaperWhiteNits) || PaperWhiteNits <= 0.f || PaperWhiteNits > PeakNits)
    {
        OutError = TEXT("Filmic HDR paper white must be finite, positive and no greater than the peak.");
        return false;
    }
    return true;
}

void UMoviePipelineFilmicHDRSetting::ValidateStateImpl()
{
    Super::ValidateStateImpl();
    FString Error;
    if (!ValidateConfiguration(Error))
    {
        ValidationState = EMoviePipelineValidationState::Errors;
        ValidationResults.Add(FText::FromString(Error));
    }
}

void UMoviePipelineFilmicHDRSetting::SetupForPipelineImpl(UMoviePipeline* InPipeline)
{
    FString Error;
    if (!ValidateConfiguration(Error))
    {
        UE_LOG(LogMineprepDisplayHDR, Error, TEXT("%s"), *Error);
        if (InPipeline)
        {
            InPipeline->RequestShutdown(true);
        }
        return;
    }
    AppliedConsoleVariables = NewObject<UMoviePipelineConsoleVariableSetting>(this);
    AppliedConsoleVariables->AddOrUpdateConsoleVariable(TEXT("r.LUT.TonemappingMethod"), static_cast<float>(ETonemappingMethod::Filmic));
    AppliedConsoleVariables->OnMoviePipelineInitialized(InPipeline);
}

void UMoviePipelineFilmicHDRSetting::SetupViewFamily(FSceneViewFamily& ViewFamily)
{
    // Parameters were validated before initialization.
    if (!ViewFamily.RenderTarget)
    {
        UE_LOG(LogMineprepDisplayHDR, Error, TEXT("Cannot configure Filmic HDR without an MRQ render target."));
        return;
    }
    const FRenderTarget* Original = ViewFamily.RenderTarget;
    TSharedPtr<FMineprepDisplayHDRRenderTarget>& Proxy = RenderTargets.FindOrAdd(Original);
    if (!Proxy)
    {
        Proxy = MakeShared<FMineprepDisplayHDRRenderTarget>(*Original, PeakNits, PaperWhiteNits, bOutputPQ);
    }
    ViewFamily.RenderTarget = Proxy.Get();
    // Avoid FinalColorHDR/FinalToneCurveHDR forcing the 100-nit linear output device.
    ViewFamily.SceneCaptureSource = SCS_FinalColorLDR;
    ViewFamily.EngineShowFlags.SetToneCurve(true);
}

void UMoviePipelineFilmicHDRSetting::ReleaseRuntimeState()
{
    if (!RenderTargets.IsEmpty())
    {
        FlushRenderingCommands();
        RenderTargets.Empty();
    }
    if (AppliedConsoleVariables)
    {
        AppliedConsoleVariables->OnMoviePipelineShutdown(GetPipeline());
        AppliedConsoleVariables = nullptr;
    }
}

void UMoviePipelineFilmicHDRSetting::TeardownForPipelineImpl(UMoviePipeline* InPipeline)
{
    ReleaseRuntimeState();
}

void UMoviePipelineFilmicHDRSetting::OnSetupForShotImpl(UMoviePipelineExecutorShot* InShot)
{
    if (!AppliedConsoleVariables)
    {
        SetupForPipelineImpl(GetPipeline());
    }
}

void UMoviePipelineFilmicHDRSetting::OnTeardownForShotImpl(UMoviePipelineExecutorShot* InShot)
{
    // Release per-shot targets and restore Filmic; the next shot reapplies it.
    // Pipeline teardown remains a fallback for failure and cancellation.
    ReleaseRuntimeState();
}

void UMoviePipelineFilmicHDRSetting::BeginDestroy()
{
    ReleaseRuntimeState();
    Super::BeginDestroy();
}

void UMoviePipelineFilmicHDRSetting::GetFormatArguments(FMoviePipelineFormatArgs& InOutFormatArgs) const
{
    Super::GetFormatArguments(InOutFormatArgs);
    InOutFormatArgs.FileMetadata.Add(TEXT("mineprep/displayHDR/encoding"), bOutputPQ ? TEXT("Rec.2020 D65; ST2084 PQ") : TEXT("linear scRGB; 1.0 = 80 cd/m2"));
    InOutFormatArgs.FileMetadata.Add(TEXT("mineprep/displayHDR/peakNits"), FString::SanitizeFloat(PeakNits));
    InOutFormatArgs.FileMetadata.Add(TEXT("mineprep/displayHDR/paperWhiteNits"), FString::SanitizeFloat(PaperWhiteNits));
    InOutFormatArgs.FileMetadata.Add(TEXT("mineprep/displayHDR/limitingGamut"), TEXT("Rec.2020 D65"));
}

#if WITH_EDITOR
FText UMoviePipelineFilmicHDRSetting::GetDisplayText() const
{
    return NSLOCTEXT("Mineprep", "MoviePipelineFilmicHDR", "Mineprep Filmic HDR");
}
#endif
