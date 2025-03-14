// Copyright Epic Games, Inc. All Rights Reserved.

#include "MovieGraphObjectIdNode.h"

#include "Editor/EditorPerProjectUserSettings.h"
#include "MovieGraphObjectIdPass.h"
#include "MoviePipelineTelemetry.h"

FEngineShowFlags UMovieGraphObjectIdNode::GetShowFlags() const
{
	FEngineShowFlags Flags(ESFIM_Game);
	Flags.DisableAdvancedFeatures();
	Flags.SetPostProcessing(false);
	Flags.SetPostProcessMaterial(false);

	// The most important flag. The Hit Proxy IDs will be used to generate Object IDs.
	Flags.SetHitProxies(true);

	// Screen-percentage scaling mixes IDs when doing down-sampling, so it is disabled.
	Flags.SetScreenPercentage(false);

	return Flags;
}

EViewModeIndex UMovieGraphObjectIdNode::GetViewModeIndex() const
{
	return VMI_Unlit;
}

bool UMovieGraphObjectIdNode::GetAllowsShowFlagsCustomization() const
{
	return false;
}

bool UMovieGraphObjectIdNode::GetAllowsCompositing() const
{
	// Having anything composited into an Object ID pass would corrupt the data in it
	return false;
}

#if WITH_EDITOR
FText UMovieGraphObjectIdNode::GetNodeTitle(const bool bGetDescriptive) const
{
	return NSLOCTEXT("MovieRenderGraph", "ObjectIdNodeTitle", "Object IDs");		
}

FSlateIcon UMovieGraphObjectIdNode::GetIconAndTint(FLinearColor& OutColor) const
{
	static const FSlateIcon DeferredRendererIcon = FSlateIcon(FAppStyle::GetAppStyleSetName(), "ContentBrowser.SizeMap");
	OutColor = FLinearColor::White;
	
	return DeferredRendererIcon;
}
#endif	// WITH_EDITOR

void UMovieGraphObjectIdNode::UpdateTelemetry(FMoviePipelineShotRenderTelemetry* InTelemetry) const
{
	InTelemetry->bUsesObjectID = true;
}

TUniquePtr<UE::MovieGraph::Rendering::FMovieGraphImagePassBase> UMovieGraphObjectIdNode::CreateInstance() const
{
	return MakeUnique<FMovieGraphObjectIdPass>();
}

FString UMovieGraphObjectIdNode::GetRendererNameImpl() const
{
	return TEXT("ObjectID");
}

void UMovieGraphObjectIdNode::SetupImpl(const FMovieGraphRenderPassSetupData& InSetupData)
{
	Super::SetupImpl(InSetupData);

#if WITH_EDITOR
	UEditorPerProjectUserSettings* EditorSettings = GetMutableDefault<UEditorPerProjectUserSettings>();
	bPrevAllowSelectTranslucent = EditorSettings->bAllowSelectTranslucent;
	EditorSettings->bAllowSelectTranslucent = bIncludeTranslucentObjects;
#endif
}

void UMovieGraphObjectIdNode::TeardownImpl()
{
#if WITH_EDITOR
	UEditorPerProjectUserSettings* EditorSettings = GetMutableDefault<UEditorPerProjectUserSettings>();
	EditorSettings->bAllowSelectTranslucent = bPrevAllowSelectTranslucent;
#endif
	
	Super::TeardownImpl();
}
