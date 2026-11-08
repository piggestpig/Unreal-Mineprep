#pragma once

#include "CoreMinimal.h"
#include "MoviePipelineViewFamilySetting.h"
#include "MoviePipelineFilmicHDRSetting.generated.h"

class FRenderTarget;
class FMineprepDisplayHDRRenderTarget;
class UMoviePipelineConsoleVariableSetting;

/** Native Filmic HDR output, with user-controlled rendering and color settings. */
UCLASS(BlueprintType, meta=(DisplayName="Mineprep Filmic HDR"))
class MINEPREP_API UMoviePipelineFilmicHDRSetting : public UMoviePipelineViewFamilySetting
{
    GENERATED_BODY()

public:
    UMoviePipelineFilmicHDRSetting();
    virtual ~UMoviePipelineFilmicHDRSetting() override;

    /** Output Rec.2020/D65 ST2084 PQ; disable for linear scRGB (1.0 = 80 nits). */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Filmic HDR", meta=(DisplayName="Output PQ"))
    bool bOutputPQ = true;

    /** Target peak for the native Filmic HDR transform; not the connected monitor's peak. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Filmic HDR",
        meta=(DisplayName="Peak Luminance (nits)", ClampMin="100.001", ClampMax="10000.0"))
    float PeakNits = 1000.f;

    /** HDR reference white parameter. Filmic style and exposure remain controlled by the scene. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Filmic HDR",
        meta=(DisplayName="Paper White (nits)", ClampMin="0.001", ClampMax="10000.0"))
    float PaperWhiteNits = 203.f;

    virtual bool IsValidOnShots() const override { return false; }
    virtual bool IsValidOnPrimary() const override { return true; }
    // Select Filmic after ordinary game/quality settings.
    virtual int32 GetPriority() const override { return 2; }
    virtual void SetupViewFamily(FSceneViewFamily& ViewFamily) override;
    virtual void ValidateStateImpl() override;
    virtual void GetFormatArguments(FMoviePipelineFormatArgs& InOutFormatArgs) const override;
    virtual void BeginDestroy() override;

#if WITH_EDITOR
    virtual FText GetDisplayText() const override;
#endif

protected:
    virtual void SetupForPipelineImpl(UMoviePipeline* InPipeline) override;
    virtual void TeardownForPipelineImpl(UMoviePipeline* InPipeline) override;
    virtual void OnSetupForShotImpl(UMoviePipelineExecutorShot* InShot) override;
    virtual void OnTeardownForShotImpl(UMoviePipelineExecutorShot* InShot) override;

private:
    bool ValidateConfiguration(FString& OutError) const;
    void ReleaseRuntimeState();

    UPROPERTY(Transient)
    TObjectPtr<UMoviePipelineConsoleVariableSetting> AppliedConsoleVariables;

    TMap<const FRenderTarget*, TSharedPtr<FMineprepDisplayHDRRenderTarget>> RenderTargets;
};
