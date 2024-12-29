// Copyright Epic Games, Inc. All Rights Reserved.
/*===========================================================================
	Generated code exported from UnrealHeaderTool.
	DO NOT modify this manually! Edit the corresponding .h files instead!
===========================================================================*/

#include "UObject/GeneratedCppIncludes.h"
#include "MoviePipelineMaskRenderPass/Private/MoviePipelinePanoramicPass.h"
PRAGMA_DISABLE_DEPRECATION_WARNINGS
void EmptyLinkFunctionForGeneratedCodeMoviePipelinePanoramicPass() {}

// Begin Cross Module References
MOVIEPIPELINEMASKRENDERPASS_API UClass* Z_Construct_UClass_UMoviePipelinePanoramicPass();
MOVIEPIPELINEMASKRENDERPASS_API UClass* Z_Construct_UClass_UMoviePipelinePanoramicPass_NoRegister();
MOVIERENDERPIPELINERENDERPASSES_API UClass* Z_Construct_UClass_UMoviePipelineImagePassBase();
UPackage* Z_Construct_UPackage__Script_MoviePipelineMaskRenderPass();
// End Cross Module References

// Begin Class UMoviePipelinePanoramicPass
void UMoviePipelinePanoramicPass::StaticRegisterNativesUMoviePipelinePanoramicPass()
{
}
IMPLEMENT_CLASS_NO_AUTO_REGISTRATION(UMoviePipelinePanoramicPass);
UClass* Z_Construct_UClass_UMoviePipelinePanoramicPass_NoRegister()
{
	return UMoviePipelinePanoramicPass::StaticClass();
}
struct Z_Construct_UClass_UMoviePipelinePanoramicPass_Statics
{
#if WITH_METADATA
	static constexpr UECodeGen_Private::FMetaDataPairParam Class_MetaDataParams[] = {
		{ "BlueprintType", "true" },
#if !UE_BUILD_SHIPPING
		{ "Comment", "/**\n* Generates a panoramic image (potentially in stereo, stored top/bottom in the final sheet) in equirectangular projection space.\n* Each render is a traditional 2D render and then they are blended together afterwards. For each horizontal step we render n\n* many vertical steps. Each of these renders is called a 'Pane' to avoid confusion with the High Resolution 'Tiles' which only apply to 2D.\n*/" },
#endif
		{ "IncludePath", "MoviePipelinePanoramicPass.h" },
		{ "ModuleRelativePath", "Private/MoviePipelinePanoramicPass.h" },
#if !UE_BUILD_SHIPPING
		{ "ToolTip", "Generates a panoramic image (potentially in stereo, stored top/bottom in the final sheet) in equirectangular projection space.\nEach render is a traditional 2D render and then they are blended together afterwards. For each horizontal step we render n\nmany vertical steps. Each of these renders is called a 'Pane' to avoid confusion with the High Resolution 'Tiles' which only apply to 2D." },
#endif
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_NumHorizontalSteps_MetaData[] = {
		{ "Category", "Panoramic Settings" },
		{ "ClampMin", "1" },
#if !UE_BUILD_SHIPPING
		{ "Comment", "/**\n\x09* How many different renders should the 360* horizontal view be broken into? Higher numbers are less distorted but longer to render.\n\x09*/" },
#endif
		{ "ModuleRelativePath", "Private/MoviePipelinePanoramicPass.h" },
#if !UE_BUILD_SHIPPING
		{ "ToolTip", "How many different renders should the 360* horizontal view be broken into? Higher numbers are less distorted but longer to render." },
#endif
		{ "UIMin", "1" },
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_NumVerticalSteps_MetaData[] = {
		{ "Category", "Panoramic Settings" },
		{ "ClampMin", "1" },
#if !UE_BUILD_SHIPPING
		{ "Comment", "/**\n\x09* How many different renders should the 360* vertical view be broken into? Higher numbers are less distorted but longer to render.\n\x09* This is typically less than horizontal as the vertical poles of an image will always have distortion in equirectangular projections.\n\x09*/" },
#endif
		{ "ModuleRelativePath", "Private/MoviePipelinePanoramicPass.h" },
#if !UE_BUILD_SHIPPING
		{ "ToolTip", "How many different renders should the 360* vertical view be broken into? Higher numbers are less distorted but longer to render.\nThis is typically less than horizontal as the vertical poles of an image will always have distortion in equirectangular projections." },
#endif
		{ "UIMin", "1" },
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_bFollowCameraOrientation_MetaData[] = {
		{ "Category", "Panoramic Settings" },
#if !UE_BUILD_SHIPPING
		{ "Comment", "/**\n\x09* Should the Pitch, Yaw and Roll of the camera be respected? If false, only the location will be taken from the camera.\n\x09*/" },
#endif
		{ "ModuleRelativePath", "Private/MoviePipelinePanoramicPass.h" },
#if !UE_BUILD_SHIPPING
		{ "ToolTip", "Should the Pitch, Yaw and Roll of the camera be respected? If false, only the location will be taken from the camera." },
#endif
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_bStereo_MetaData[] = {
		{ "Category", "Panoramic Settings" },
#if !UE_BUILD_SHIPPING
		{ "Comment", "/**\n\x09* If true we will capture a stereo panorama. This doubles everything (all render times, memory requirements, etc.)\n\x09* May need a significantly higher number of horizontal steps to look good when viewed in stereo.\n\x09*/" },
#endif
		{ "ModuleRelativePath", "Private/MoviePipelinePanoramicPass.h" },
#if !UE_BUILD_SHIPPING
		{ "ToolTip", "If true we will capture a stereo panorama. This doubles everything (all render times, memory requirements, etc.)\nMay need a significantly higher number of horizontal steps to look good when viewed in stereo." },
#endif
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_EyeSeparation_MetaData[] = {
		{ "Category", "Panoramic Settings" },
		{ "ModuleRelativePath", "Private/MoviePipelinePanoramicPass.h" },
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_EyeConvergenceDistance_MetaData[] = {
		{ "Category", "Panoramic Settings" },
		{ "ModuleRelativePath", "Private/MoviePipelinePanoramicPass.h" },
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_HorzFieldOfView_MetaData[] = {
		{ "Category", "Panoramic Settings" },
#if !UE_BUILD_SHIPPING
		{ "Comment", "/**Advance used only. Allows you to override the Horizontal Field of View (if not zero). Can cause crashes or incomplete panoramas.*/" },
#endif
		{ "ModuleRelativePath", "Private/MoviePipelinePanoramicPass.h" },
#if !UE_BUILD_SHIPPING
		{ "ToolTip", "Advance used only. Allows you to override the Horizontal Field of View (if not zero). Can cause crashes or incomplete panoramas." },
#endif
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_VertFieldOfView_MetaData[] = {
		{ "Category", "Panoramic Settings" },
#if !UE_BUILD_SHIPPING
		{ "Comment", "/**Advance used only. Allows you to override the Vertical Field of View (if not zero). Can cause crashes or incomplete panoramas.*/" },
#endif
		{ "ModuleRelativePath", "Private/MoviePipelinePanoramicPass.h" },
#if !UE_BUILD_SHIPPING
		{ "ToolTip", "Advance used only. Allows you to override the Vertical Field of View (if not zero). Can cause crashes or incomplete panoramas." },
#endif
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_bAllocateHistoryPerPane_MetaData[] = {
		{ "Category", "Panoramic Settings" },
#if !UE_BUILD_SHIPPING
		{ "Comment", "/**\n\x09* Should we store the render scene history per individual render? This can consume a great deal of memory with many renders,\n\x09* but enables TAA and other history-based effects (denoisers, etc.) to work.\n\x09*/" },
#endif
		{ "ModuleRelativePath", "Private/MoviePipelinePanoramicPass.h" },
#if !UE_BUILD_SHIPPING
		{ "ToolTip", "Should we store the render scene history per individual render? This can consume a great deal of memory with many renders,\nbut enables TAA and other history-based effects (denoisers, etc.) to work." },
#endif
	};
#endif // WITH_METADATA
	static const UECodeGen_Private::FIntPropertyParams NewProp_NumHorizontalSteps;
	static const UECodeGen_Private::FIntPropertyParams NewProp_NumVerticalSteps;
	static void NewProp_bFollowCameraOrientation_SetBit(void* Obj);
	static const UECodeGen_Private::FBoolPropertyParams NewProp_bFollowCameraOrientation;
	static void NewProp_bStereo_SetBit(void* Obj);
	static const UECodeGen_Private::FBoolPropertyParams NewProp_bStereo;
	static const UECodeGen_Private::FFloatPropertyParams NewProp_EyeSeparation;
	static const UECodeGen_Private::FFloatPropertyParams NewProp_EyeConvergenceDistance;
	static const UECodeGen_Private::FFloatPropertyParams NewProp_HorzFieldOfView;
	static const UECodeGen_Private::FFloatPropertyParams NewProp_VertFieldOfView;
	static void NewProp_bAllocateHistoryPerPane_SetBit(void* Obj);
	static const UECodeGen_Private::FBoolPropertyParams NewProp_bAllocateHistoryPerPane;
	static const UECodeGen_Private::FPropertyParamsBase* const PropPointers[];
	static UObject* (*const DependentSingletons[])();
	static constexpr FCppClassTypeInfoStatic StaticCppClassTypeInfo = {
		TCppClassTypeTraits<UMoviePipelinePanoramicPass>::IsAbstract,
	};
	static const UECodeGen_Private::FClassParams ClassParams;
};
const UECodeGen_Private::FIntPropertyParams Z_Construct_UClass_UMoviePipelinePanoramicPass_Statics::NewProp_NumHorizontalSteps = { "NumHorizontalSteps", nullptr, (EPropertyFlags)0x0010000000000005, UECodeGen_Private::EPropertyGenFlags::Int, RF_Public|RF_Transient|RF_MarkAsNative, nullptr, nullptr, 1, STRUCT_OFFSET(UMoviePipelinePanoramicPass, NumHorizontalSteps), METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_NumHorizontalSteps_MetaData), NewProp_NumHorizontalSteps_MetaData) };
const UECodeGen_Private::FIntPropertyParams Z_Construct_UClass_UMoviePipelinePanoramicPass_Statics::NewProp_NumVerticalSteps = { "NumVerticalSteps", nullptr, (EPropertyFlags)0x0010000000000005, UECodeGen_Private::EPropertyGenFlags::Int, RF_Public|RF_Transient|RF_MarkAsNative, nullptr, nullptr, 1, STRUCT_OFFSET(UMoviePipelinePanoramicPass, NumVerticalSteps), METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_NumVerticalSteps_MetaData), NewProp_NumVerticalSteps_MetaData) };
void Z_Construct_UClass_UMoviePipelinePanoramicPass_Statics::NewProp_bFollowCameraOrientation_SetBit(void* Obj)
{
	((UMoviePipelinePanoramicPass*)Obj)->bFollowCameraOrientation = 1;
}
const UECodeGen_Private::FBoolPropertyParams Z_Construct_UClass_UMoviePipelinePanoramicPass_Statics::NewProp_bFollowCameraOrientation = { "bFollowCameraOrientation", nullptr, (EPropertyFlags)0x0010000000000005, UECodeGen_Private::EPropertyGenFlags::Bool | UECodeGen_Private::EPropertyGenFlags::NativeBool, RF_Public|RF_Transient|RF_MarkAsNative, nullptr, nullptr, 1, sizeof(bool), sizeof(UMoviePipelinePanoramicPass), &Z_Construct_UClass_UMoviePipelinePanoramicPass_Statics::NewProp_bFollowCameraOrientation_SetBit, METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_bFollowCameraOrientation_MetaData), NewProp_bFollowCameraOrientation_MetaData) };
void Z_Construct_UClass_UMoviePipelinePanoramicPass_Statics::NewProp_bStereo_SetBit(void* Obj)
{
	((UMoviePipelinePanoramicPass*)Obj)->bStereo = 1;
}
const UECodeGen_Private::FBoolPropertyParams Z_Construct_UClass_UMoviePipelinePanoramicPass_Statics::NewProp_bStereo = { "bStereo", nullptr, (EPropertyFlags)0x0010000000000005, UECodeGen_Private::EPropertyGenFlags::Bool | UECodeGen_Private::EPropertyGenFlags::NativeBool, RF_Public|RF_Transient|RF_MarkAsNative, nullptr, nullptr, 1, sizeof(bool), sizeof(UMoviePipelinePanoramicPass), &Z_Construct_UClass_UMoviePipelinePanoramicPass_Statics::NewProp_bStereo_SetBit, METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_bStereo_MetaData), NewProp_bStereo_MetaData) };
const UECodeGen_Private::FFloatPropertyParams Z_Construct_UClass_UMoviePipelinePanoramicPass_Statics::NewProp_EyeSeparation = { "EyeSeparation", nullptr, (EPropertyFlags)0x0010040000000005, UECodeGen_Private::EPropertyGenFlags::Float, RF_Public|RF_Transient|RF_MarkAsNative, nullptr, nullptr, 1, STRUCT_OFFSET(UMoviePipelinePanoramicPass, EyeSeparation), METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_EyeSeparation_MetaData), NewProp_EyeSeparation_MetaData) };
const UECodeGen_Private::FFloatPropertyParams Z_Construct_UClass_UMoviePipelinePanoramicPass_Statics::NewProp_EyeConvergenceDistance = { "EyeConvergenceDistance", nullptr, (EPropertyFlags)0x0010040000000005, UECodeGen_Private::EPropertyGenFlags::Float, RF_Public|RF_Transient|RF_MarkAsNative, nullptr, nullptr, 1, STRUCT_OFFSET(UMoviePipelinePanoramicPass, EyeConvergenceDistance), METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_EyeConvergenceDistance_MetaData), NewProp_EyeConvergenceDistance_MetaData) };
const UECodeGen_Private::FFloatPropertyParams Z_Construct_UClass_UMoviePipelinePanoramicPass_Statics::NewProp_HorzFieldOfView = { "HorzFieldOfView", nullptr, (EPropertyFlags)0x0010040000000005, UECodeGen_Private::EPropertyGenFlags::Float, RF_Public|RF_Transient|RF_MarkAsNative, nullptr, nullptr, 1, STRUCT_OFFSET(UMoviePipelinePanoramicPass, HorzFieldOfView), METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_HorzFieldOfView_MetaData), NewProp_HorzFieldOfView_MetaData) };
const UECodeGen_Private::FFloatPropertyParams Z_Construct_UClass_UMoviePipelinePanoramicPass_Statics::NewProp_VertFieldOfView = { "VertFieldOfView", nullptr, (EPropertyFlags)0x0010040000000005, UECodeGen_Private::EPropertyGenFlags::Float, RF_Public|RF_Transient|RF_MarkAsNative, nullptr, nullptr, 1, STRUCT_OFFSET(UMoviePipelinePanoramicPass, VertFieldOfView), METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_VertFieldOfView_MetaData), NewProp_VertFieldOfView_MetaData) };
void Z_Construct_UClass_UMoviePipelinePanoramicPass_Statics::NewProp_bAllocateHistoryPerPane_SetBit(void* Obj)
{
	((UMoviePipelinePanoramicPass*)Obj)->bAllocateHistoryPerPane = 1;
}
const UECodeGen_Private::FBoolPropertyParams Z_Construct_UClass_UMoviePipelinePanoramicPass_Statics::NewProp_bAllocateHistoryPerPane = { "bAllocateHistoryPerPane", nullptr, (EPropertyFlags)0x0010040000000005, UECodeGen_Private::EPropertyGenFlags::Bool | UECodeGen_Private::EPropertyGenFlags::NativeBool, RF_Public|RF_Transient|RF_MarkAsNative, nullptr, nullptr, 1, sizeof(bool), sizeof(UMoviePipelinePanoramicPass), &Z_Construct_UClass_UMoviePipelinePanoramicPass_Statics::NewProp_bAllocateHistoryPerPane_SetBit, METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_bAllocateHistoryPerPane_MetaData), NewProp_bAllocateHistoryPerPane_MetaData) };
const UECodeGen_Private::FPropertyParamsBase* const Z_Construct_UClass_UMoviePipelinePanoramicPass_Statics::PropPointers[] = {
	(const UECodeGen_Private::FPropertyParamsBase*)&Z_Construct_UClass_UMoviePipelinePanoramicPass_Statics::NewProp_NumHorizontalSteps,
	(const UECodeGen_Private::FPropertyParamsBase*)&Z_Construct_UClass_UMoviePipelinePanoramicPass_Statics::NewProp_NumVerticalSteps,
	(const UECodeGen_Private::FPropertyParamsBase*)&Z_Construct_UClass_UMoviePipelinePanoramicPass_Statics::NewProp_bFollowCameraOrientation,
	(const UECodeGen_Private::FPropertyParamsBase*)&Z_Construct_UClass_UMoviePipelinePanoramicPass_Statics::NewProp_bStereo,
	(const UECodeGen_Private::FPropertyParamsBase*)&Z_Construct_UClass_UMoviePipelinePanoramicPass_Statics::NewProp_EyeSeparation,
	(const UECodeGen_Private::FPropertyParamsBase*)&Z_Construct_UClass_UMoviePipelinePanoramicPass_Statics::NewProp_EyeConvergenceDistance,
	(const UECodeGen_Private::FPropertyParamsBase*)&Z_Construct_UClass_UMoviePipelinePanoramicPass_Statics::NewProp_HorzFieldOfView,
	(const UECodeGen_Private::FPropertyParamsBase*)&Z_Construct_UClass_UMoviePipelinePanoramicPass_Statics::NewProp_VertFieldOfView,
	(const UECodeGen_Private::FPropertyParamsBase*)&Z_Construct_UClass_UMoviePipelinePanoramicPass_Statics::NewProp_bAllocateHistoryPerPane,
};
static_assert(UE_ARRAY_COUNT(Z_Construct_UClass_UMoviePipelinePanoramicPass_Statics::PropPointers) < 2048);
UObject* (*const Z_Construct_UClass_UMoviePipelinePanoramicPass_Statics::DependentSingletons[])() = {
	(UObject* (*)())Z_Construct_UClass_UMoviePipelineImagePassBase,
	(UObject* (*)())Z_Construct_UPackage__Script_MoviePipelineMaskRenderPass,
};
static_assert(UE_ARRAY_COUNT(Z_Construct_UClass_UMoviePipelinePanoramicPass_Statics::DependentSingletons) < 16);
const UECodeGen_Private::FClassParams Z_Construct_UClass_UMoviePipelinePanoramicPass_Statics::ClassParams = {
	&UMoviePipelinePanoramicPass::StaticClass,
	nullptr,
	&StaticCppClassTypeInfo,
	DependentSingletons,
	nullptr,
	Z_Construct_UClass_UMoviePipelinePanoramicPass_Statics::PropPointers,
	nullptr,
	UE_ARRAY_COUNT(DependentSingletons),
	0,
	UE_ARRAY_COUNT(Z_Construct_UClass_UMoviePipelinePanoramicPass_Statics::PropPointers),
	0,
	0x000000A0u,
	METADATA_PARAMS(UE_ARRAY_COUNT(Z_Construct_UClass_UMoviePipelinePanoramicPass_Statics::Class_MetaDataParams), Z_Construct_UClass_UMoviePipelinePanoramicPass_Statics::Class_MetaDataParams)
};
UClass* Z_Construct_UClass_UMoviePipelinePanoramicPass()
{
	if (!Z_Registration_Info_UClass_UMoviePipelinePanoramicPass.OuterSingleton)
	{
		UECodeGen_Private::ConstructUClass(Z_Registration_Info_UClass_UMoviePipelinePanoramicPass.OuterSingleton, Z_Construct_UClass_UMoviePipelinePanoramicPass_Statics::ClassParams);
	}
	return Z_Registration_Info_UClass_UMoviePipelinePanoramicPass.OuterSingleton;
}
template<> MOVIEPIPELINEMASKRENDERPASS_API UClass* StaticClass<UMoviePipelinePanoramicPass>()
{
	return UMoviePipelinePanoramicPass::StaticClass();
}
DEFINE_VTABLE_PTR_HELPER_CTOR(UMoviePipelinePanoramicPass);
UMoviePipelinePanoramicPass::~UMoviePipelinePanoramicPass() {}
// End Class UMoviePipelinePanoramicPass

// Begin Registration
struct Z_CompiledInDeferFile_FID_Mineprep_last_0_4_Plugins_MoviePipelineMaskRenderPass_Source_MoviePipelineMaskRenderPass_Private_MoviePipelinePanoramicPass_h_Statics
{
	static constexpr FClassRegisterCompiledInInfo ClassInfo[] = {
		{ Z_Construct_UClass_UMoviePipelinePanoramicPass, UMoviePipelinePanoramicPass::StaticClass, TEXT("UMoviePipelinePanoramicPass"), &Z_Registration_Info_UClass_UMoviePipelinePanoramicPass, CONSTRUCT_RELOAD_VERSION_INFO(FClassReloadVersionInfo, sizeof(UMoviePipelinePanoramicPass), 1707637252U) },
	};
};
static FRegisterCompiledInInfo Z_CompiledInDeferFile_FID_Mineprep_last_0_4_Plugins_MoviePipelineMaskRenderPass_Source_MoviePipelineMaskRenderPass_Private_MoviePipelinePanoramicPass_h_3475586898(TEXT("/Script/MoviePipelineMaskRenderPass"),
	Z_CompiledInDeferFile_FID_Mineprep_last_0_4_Plugins_MoviePipelineMaskRenderPass_Source_MoviePipelineMaskRenderPass_Private_MoviePipelinePanoramicPass_h_Statics::ClassInfo, UE_ARRAY_COUNT(Z_CompiledInDeferFile_FID_Mineprep_last_0_4_Plugins_MoviePipelineMaskRenderPass_Source_MoviePipelineMaskRenderPass_Private_MoviePipelinePanoramicPass_h_Statics::ClassInfo),
	nullptr, 0,
	nullptr, 0);
// End Registration
PRAGMA_ENABLE_DEPRECATION_WARNINGS
