// Copyright Epic Games, Inc. All Rights Reserved.

#pragma once

#include "MoviePipelineObjectIdUtils.h"
#include "Graph/Nodes/MovieGraphImagePassBaseNode.h"

#include "MovieGraphObjectIdNode.generated.h"

enum class EMoviePipelineObjectIdPassIdType : uint8;

/** A node which outputs layers compatible with the Cryptomatte standard. */
UCLASS(BlueprintType)
class MOVIEPIPELINEMASKRENDERPASS_API UMovieGraphObjectIdNode final : public UMovieGraphImagePassBaseNode
{
	GENERATED_BODY()

public:
	UMovieGraphObjectIdNode() = default;

	// UMovieGraphImagePassBaseNode Interface
	virtual FEngineShowFlags GetShowFlags() const override;
	virtual EViewModeIndex GetViewModeIndex() const override;
	virtual bool GetAllowsShowFlagsCustomization() const override;
	virtual bool GetAllowsCompositing() const override;
	virtual int32 GetNumSpatialSamples() const override { return SpatialSampleCount; }
	virtual int32 GetNumSpatialSamplesDuringWarmUp() const  override { return 0; }
	// The ObjectID pass doesn't support any anti-aliasing so we force it to None so that their spatial samples turn into MRG-based camera jitter.
	virtual bool GetOverrideAntiAliasing() const override { return true; }
	virtual EAntiAliasingMethod GetAntiAliasingMethod() const override { return EAntiAliasingMethod::AAM_None; }
	// ~UMovieGraphImagePassBaseNode Interface

	// UMovieGraphNode Interface
#if WITH_EDITOR
	virtual FText GetNodeTitle(const bool bGetDescriptive = false) const override;
	virtual FSlateIcon GetIconAndTint(FLinearColor& OutColor) const override;
#endif
	// ~UMovieGraphNode Interface

	virtual void UpdateTelemetry(FMoviePipelineShotRenderTelemetry* InTelemetry) const override;

protected:
	// UMovieGraphImagePassBaseNode Interface
	virtual TUniquePtr<UE::MovieGraph::Rendering::FMovieGraphImagePassBase> CreateInstance() const override;
	// ~UMovieGraphImagePassBaseNode Interface

	// UMovieGraphRenderPassNode Interface
	virtual FString GetRendererNameImpl() const override;
	virtual void SetupImpl(const FMovieGraphRenderPassSetupData& InSetupData) override;
	virtual void TeardownImpl() override;
	// ~UMovieGraphRenderPassNode Interface

public:
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = Overrides, meta = (InlineEditConditionToggle))
	uint8 bOverride_SpatialSampleCount : 1;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = Overrides, meta = (InlineEditConditionToggle))
	uint8 bOverride_IdType : 1;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = Overrides, meta = (InlineEditConditionToggle))
	uint8 bOverride_bIncludeTranslucentObjects : 1;

	/**
	* How many sub-pixel jitter renders should we do per temporal sample? This can be used to achieve high
	* sample counts without Temporal Sub-Sampling (allowing high sample counts without motion blur being enabled).
	*/
	UPROPERTY(EditAnywhere, BlueprintReadWrite, meta = (UIMin = 1, ClampMin = 1), Category = "Settings", meta = (EditCondition = "bOverride_SpatialSampleCount"))
	int32 SpatialSampleCount = 1;

	/** How objects are grouped together within the Cryptomatte. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Settings", DisplayName = "ID Type", meta = (EditCondition="bOverride_IdType"))
	EMoviePipelineObjectIdPassIdType IdType = EMoviePipelineObjectIdPassIdType::Full;

	/** If true, translucent objects will be included in the ObjectId pass (but as an opaque layer due to limitations). False will omit translucent objects. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Settings", meta = (EditCondition="bOverride_bIncludeTranslucentObjects"))
	bool bIncludeTranslucentObjects = false;

private:
	/**
	 * The prior value of the project's bAllowSelectTranslucent setting. This node will temporarily change the value of this property to the value
	 * set in bIncludeTranslucentObjects while rendering.
	 */
	bool bPrevAllowSelectTranslucent;
};