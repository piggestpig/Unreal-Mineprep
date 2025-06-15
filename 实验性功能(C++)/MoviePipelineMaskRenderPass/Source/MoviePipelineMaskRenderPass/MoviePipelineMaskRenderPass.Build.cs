// Copyright Epic Games, Inc. All Rights Reserved.

using UnrealBuildTool;

public class MoviePipelineMaskRenderPass : ModuleRules
{
	public MoviePipelineMaskRenderPass(ReadOnlyTargetRules Target) : base(Target)
	{
		PrivateDependencyModuleNames.AddRange(
			new string[] {
				"Core",
				"CoreUObject",
				"Engine",
				"Json",
				"ImageCore",
				"MovieScene",
			}
		);

		PublicDependencyModuleNames.AddRange(
			new string[] {
				"MovieRenderPipelineCore",
				"MovieRenderPipelineRenderPasses",
				"RenderCore",
                "RHI",
				"ActorLayerUtilities",
				"OpenColorIO",
				"SlateCore",
			}
		);

		if (Target.bBuildEditor)
		{
			PublicDependencyModuleNames.AddRange(
			new string[] { "UnrealEd" });
		}
	}
}
