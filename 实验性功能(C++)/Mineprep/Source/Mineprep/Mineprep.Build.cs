// Copyright Epic Games, Inc. All Rights Reserved.

using UnrealBuildTool;

public class Mineprep : ModuleRules
{
	public Mineprep(ReadOnlyTargetRules Target) : base(Target)
	{
		PCHUsage = ModuleRules.PCHUsageMode.UseExplicitOrSharedPCHs;
		
		PublicIncludePaths.AddRange(
			new string[] {
				// ... add public include paths required here ...
			}
			);
				
		
		PrivateIncludePaths.AddRange(
			new string[] {
				// ... add other private include paths required here ...
			}
			);
			
		
		PublicDependencyModuleNames.AddRange(
			new string[] 
			{
				"Core",
				// ... add other public dependencies that you statically link with here ...
				"Slate",
				"SlateCore",
				"InputCore", // 添加 InputCore 模块依赖
				"Niagara", // 添加 Niagara 模块依赖
				"PhysicsCore", // 添加 PhysicsCore 模块依赖
			}
			);
			
		
		PrivateDependencyModuleNames.AddRange(
			new string[] 
			{
				"CoreUObject",
				"Engine",
				"Slate",
				"SlateCore",
				"Blutility",
				"UnrealEd",
				"AppFramework",
				"ToolWidgets",
				"LevelEditor",
				"PropertyEditor",
				"MovieSceneTracks",
				"SettingsEditor",
				"BlueprintGraph",
				"EditorSubsystem",
				"NiagaraEditor", // 添加 NiagaraEditor 模块依赖，用于 UNiagaraScriptVariable
				// Bevel渲染系统依赖
				"RenderCore",
				"RHI",
				"Renderer",
				"Projects",
				// ... add private dependencies that you statically link with here ...	
			}
			);
		
		
		DynamicallyLoadedModuleNames.AddRange(
			new string[] 
			{
				// ... add any modules that your module loads dynamically here ...
			}
			);
	}
}
