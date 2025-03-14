// Copyright Epic Games, Inc. All Rights Reserved.

#pragma once

#include "MoviePipelineObjectIdUtils.h"
#include "Graph/Nodes/MovieGraphImagePassBaseNode.h"

#include "MovieGraphObjectIdNode.generated.h"

enum class EMoviePipelineObjectIdPassIdType : uint8;

/** A node which outputs layers compatible with the Cryptomatte standard. */
UCLASS(BlueprintType)
class UMovieGraphObjectIdNode : public UMovieGraphImagePassBaseNode
{
	GENERATED_BODY()

public:
	UMovieGraphObjectIdNode() = default;

	// UMovieGraphImagePassBaseNode Interface
	virtual FEngineShowFlags GetShowFlags() const override;
	virtual EViewModeIndex GetViewModeIndex() const override;
	virtual bool GetAllowsShowFlagsCustomization() const override;
	virtual bool GetAllowsCompositing() const override;
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
	uint8 bOverride_IdType : 1;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = Overrides, meta = (InlineEditConditionToggle))
	uint8 bOverride_bIncludeTranslucentObjects : 1;

	/** How objects are grouped together within the Cryptomatte. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Settings", DisplayName = "ID Type", meta = (EditCondition="bOverride_IdType"))
	EMoviePipelineObjectIdPassIdType IdType;

	/** If true, translucent objects will be included in the ObjectId pass (but as an opaque layer due to limitations). False will omit translucent objects. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Settings", meta = (EditCondition="bOverride_bIncludeTranslucentObjects"))
	bool bIncludeTranslucentObjects;

private:
	/**
	 * The prior value of the project's bAllowSelectTranslucent setting. This node will temporarily change the value of this property to the value
	 * set in bIncludeTranslucentObjects while rendering.
	 */
	bool bPrevAllowSelectTranslucent;
};