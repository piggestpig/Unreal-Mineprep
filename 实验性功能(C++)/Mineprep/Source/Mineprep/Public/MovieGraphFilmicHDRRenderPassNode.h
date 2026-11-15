#pragma once

#include "CoreMinimal.h"
#include "Graph/Nodes/MovieGraphDeferredPassNode.h"
#include "MovieGraphFilmicHDRRenderPassNode.generated.h"

/** Fixed display-target HDR. Select Filmic in the graph's global CVar settings. */
UCLASS(BlueprintType, meta=(DisplayName="Mineprep Filmic HDR Renderer"))
class MINEPREP_API UMovieGraphFilmicHDRRenderPassNode : public UMovieGraphDeferredRenderPassNode
{
    GENERATED_BODY()

public:
    UMovieGraphFilmicHDRRenderPassNode();

    /** Keep runtime and editor positions aligned when generating the example asset. */
    UFUNCTION(BlueprintCallable, Category="Mineprep|Movie Graph")
    static void SetGraphNodePosition(UMovieGraphNode* Node, int32 X, int32 Y);

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category=Overrides, meta=(InlineEditConditionToggle))
    uint8 bOverride_bOutputPQ : 1;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category=Overrides, meta=(InlineEditConditionToggle))
    uint8 bOverride_PeakNits : 1;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category=Overrides, meta=(InlineEditConditionToggle))
    uint8 bOverride_PaperWhiteNits : 1;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Filmic HDR", meta=(DisplayName="Output PQ", EditCondition="bOverride_bOutputPQ"))
    bool bOutputPQ = true;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Filmic HDR", meta=(DisplayName="Peak Luminance (nits)", EditCondition="bOverride_PeakNits", ClampMin="100.001", ClampMax="10000"))
    float PeakNits = 1000.f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Filmic HDR", meta=(DisplayName="Paper White (nits)", EditCondition="bOverride_PaperWhiteNits", ClampMin="0.001", ClampMax="10000"))
    float PaperWhiteNits = 203.f;

#if WITH_EDITOR
    virtual FText GetNodeTitle(bool bGetDescriptive = false) const override;
#endif

protected:
    virtual TUniquePtr<UE::MovieGraph::Rendering::FMovieGraphImagePassBase> CreateInstance() const override;
    virtual FString GetRendererNameImpl() const override { return TEXT("FilmicHDR"); }
    virtual bool GetDisableToneCurve() const override { return false; }
};
