// Copyright Epic Games, Inc. All Rights Reserved.
/*===========================================================================
	Generated code exported from UnrealHeaderTool.
	DO NOT modify this manually! Edit the corresponding .h files instead!
===========================================================================*/

#include "UObject/GeneratedCppIncludes.h"
#include "IntroTutorials/Private/TutorialStateSettings.h"
PRAGMA_DISABLE_DEPRECATION_WARNINGS
void EmptyLinkFunctionForGeneratedCodeTutorialStateSettings() {}

// Begin Cross Module References
COREUOBJECT_API UClass* Z_Construct_UClass_UObject();
COREUOBJECT_API UScriptStruct* Z_Construct_UScriptStruct_FSoftClassPath();
INTROTUTORIALS_API UClass* Z_Construct_UClass_UTutorialStateSettings();
INTROTUTORIALS_API UClass* Z_Construct_UClass_UTutorialStateSettings_NoRegister();
INTROTUTORIALS_API UScriptStruct* Z_Construct_UScriptStruct_FTutorialProgress();
UPackage* Z_Construct_UPackage__Script_IntroTutorials();
// End Cross Module References

// Begin ScriptStruct FTutorialProgress
static FStructRegistrationInfo Z_Registration_Info_UScriptStruct_TutorialProgress;
class UScriptStruct* FTutorialProgress::StaticStruct()
{
	if (!Z_Registration_Info_UScriptStruct_TutorialProgress.OuterSingleton)
	{
		Z_Registration_Info_UScriptStruct_TutorialProgress.OuterSingleton = GetStaticStruct(Z_Construct_UScriptStruct_FTutorialProgress, (UObject*)Z_Construct_UPackage__Script_IntroTutorials(), TEXT("TutorialProgress"));
	}
	return Z_Registration_Info_UScriptStruct_TutorialProgress.OuterSingleton;
}
template<> INTROTUTORIALS_API UScriptStruct* StaticStruct<FTutorialProgress>()
{
	return FTutorialProgress::StaticStruct();
}
struct Z_Construct_UScriptStruct_FTutorialProgress_Statics
{
#if WITH_METADATA
	static constexpr UECodeGen_Private::FMetaDataPairParam Struct_MetaDataParams[] = {
#if !UE_BUILD_SHIPPING
		{ "Comment", "/** Track the progress of an individual tutorial */" },
#endif
		{ "ModuleRelativePath", "Private/TutorialStateSettings.h" },
#if !UE_BUILD_SHIPPING
		{ "ToolTip", "Track the progress of an individual tutorial" },
#endif
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_Tutorial_MetaData[] = {
		{ "ModuleRelativePath", "Private/TutorialStateSettings.h" },
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_CurrentStage_MetaData[] = {
		{ "ModuleRelativePath", "Private/TutorialStateSettings.h" },
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_bUserDismissed_MetaData[] = {
		{ "ModuleRelativePath", "Private/TutorialStateSettings.h" },
	};
#endif // WITH_METADATA
	static const UECodeGen_Private::FStructPropertyParams NewProp_Tutorial;
	static const UECodeGen_Private::FIntPropertyParams NewProp_CurrentStage;
	static void NewProp_bUserDismissed_SetBit(void* Obj);
	static const UECodeGen_Private::FBoolPropertyParams NewProp_bUserDismissed;
	static const UECodeGen_Private::FPropertyParamsBase* const PropPointers[];
	static void* NewStructOps()
	{
		return (UScriptStruct::ICppStructOps*)new UScriptStruct::TCppStructOps<FTutorialProgress>();
	}
	static const UECodeGen_Private::FStructParams StructParams;
};
const UECodeGen_Private::FStructPropertyParams Z_Construct_UScriptStruct_FTutorialProgress_Statics::NewProp_Tutorial = { "Tutorial", nullptr, (EPropertyFlags)0x0010000000000000, UECodeGen_Private::EPropertyGenFlags::Struct, RF_Public|RF_Transient|RF_MarkAsNative, nullptr, nullptr, 1, STRUCT_OFFSET(FTutorialProgress, Tutorial), Z_Construct_UScriptStruct_FSoftClassPath, METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_Tutorial_MetaData), NewProp_Tutorial_MetaData) };
const UECodeGen_Private::FIntPropertyParams Z_Construct_UScriptStruct_FTutorialProgress_Statics::NewProp_CurrentStage = { "CurrentStage", nullptr, (EPropertyFlags)0x0010000000000000, UECodeGen_Private::EPropertyGenFlags::Int, RF_Public|RF_Transient|RF_MarkAsNative, nullptr, nullptr, 1, STRUCT_OFFSET(FTutorialProgress, CurrentStage), METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_CurrentStage_MetaData), NewProp_CurrentStage_MetaData) };
void Z_Construct_UScriptStruct_FTutorialProgress_Statics::NewProp_bUserDismissed_SetBit(void* Obj)
{
	((FTutorialProgress*)Obj)->bUserDismissed = 1;
}
const UECodeGen_Private::FBoolPropertyParams Z_Construct_UScriptStruct_FTutorialProgress_Statics::NewProp_bUserDismissed = { "bUserDismissed", nullptr, (EPropertyFlags)0x0010000000000000, UECodeGen_Private::EPropertyGenFlags::Bool | UECodeGen_Private::EPropertyGenFlags::NativeBool, RF_Public|RF_Transient|RF_MarkAsNative, nullptr, nullptr, 1, sizeof(bool), sizeof(FTutorialProgress), &Z_Construct_UScriptStruct_FTutorialProgress_Statics::NewProp_bUserDismissed_SetBit, METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_bUserDismissed_MetaData), NewProp_bUserDismissed_MetaData) };
const UECodeGen_Private::FPropertyParamsBase* const Z_Construct_UScriptStruct_FTutorialProgress_Statics::PropPointers[] = {
	(const UECodeGen_Private::FPropertyParamsBase*)&Z_Construct_UScriptStruct_FTutorialProgress_Statics::NewProp_Tutorial,
	(const UECodeGen_Private::FPropertyParamsBase*)&Z_Construct_UScriptStruct_FTutorialProgress_Statics::NewProp_CurrentStage,
	(const UECodeGen_Private::FPropertyParamsBase*)&Z_Construct_UScriptStruct_FTutorialProgress_Statics::NewProp_bUserDismissed,
};
static_assert(UE_ARRAY_COUNT(Z_Construct_UScriptStruct_FTutorialProgress_Statics::PropPointers) < 2048);
const UECodeGen_Private::FStructParams Z_Construct_UScriptStruct_FTutorialProgress_Statics::StructParams = {
	(UObject* (*)())Z_Construct_UPackage__Script_IntroTutorials,
	nullptr,
	&NewStructOps,
	"TutorialProgress",
	Z_Construct_UScriptStruct_FTutorialProgress_Statics::PropPointers,
	UE_ARRAY_COUNT(Z_Construct_UScriptStruct_FTutorialProgress_Statics::PropPointers),
	sizeof(FTutorialProgress),
	alignof(FTutorialProgress),
	RF_Public|RF_Transient|RF_MarkAsNative,
	EStructFlags(0x00000001),
	METADATA_PARAMS(UE_ARRAY_COUNT(Z_Construct_UScriptStruct_FTutorialProgress_Statics::Struct_MetaDataParams), Z_Construct_UScriptStruct_FTutorialProgress_Statics::Struct_MetaDataParams)
};
UScriptStruct* Z_Construct_UScriptStruct_FTutorialProgress()
{
	if (!Z_Registration_Info_UScriptStruct_TutorialProgress.InnerSingleton)
	{
		UECodeGen_Private::ConstructUScriptStruct(Z_Registration_Info_UScriptStruct_TutorialProgress.InnerSingleton, Z_Construct_UScriptStruct_FTutorialProgress_Statics::StructParams);
	}
	return Z_Registration_Info_UScriptStruct_TutorialProgress.InnerSingleton;
}
// End ScriptStruct FTutorialProgress

// Begin Class UTutorialStateSettings
void UTutorialStateSettings::StaticRegisterNativesUTutorialStateSettings()
{
}
IMPLEMENT_CLASS_NO_AUTO_REGISTRATION(UTutorialStateSettings);
UClass* Z_Construct_UClass_UTutorialStateSettings_NoRegister()
{
	return UTutorialStateSettings::StaticClass();
}
struct Z_Construct_UClass_UTutorialStateSettings_Statics
{
#if WITH_METADATA
	static constexpr UECodeGen_Private::FMetaDataPairParam Class_MetaDataParams[] = {
#if !UE_BUILD_SHIPPING
		{ "Comment", "/** Tutorial settings used to track completion state */" },
#endif
		{ "IncludePath", "TutorialStateSettings.h" },
		{ "ModuleRelativePath", "Private/TutorialStateSettings.h" },
#if !UE_BUILD_SHIPPING
		{ "ToolTip", "Tutorial settings used to track completion state" },
#endif
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_TutorialsProgress_MetaData[] = {
		{ "ModuleRelativePath", "Private/TutorialStateSettings.h" },
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_bDismissedAllTutorials_MetaData[] = {
#if !UE_BUILD_SHIPPING
		{ "Comment", "/** Record if user has chosen to cancel all tutorials */" },
#endif
		{ "ModuleRelativePath", "Private/TutorialStateSettings.h" },
#if !UE_BUILD_SHIPPING
		{ "ToolTip", "Record if user has chosen to cancel all tutorials" },
#endif
	};
#endif // WITH_METADATA
	static const UECodeGen_Private::FStructPropertyParams NewProp_TutorialsProgress_Inner;
	static const UECodeGen_Private::FArrayPropertyParams NewProp_TutorialsProgress;
	static void NewProp_bDismissedAllTutorials_SetBit(void* Obj);
	static const UECodeGen_Private::FBoolPropertyParams NewProp_bDismissedAllTutorials;
	static const UECodeGen_Private::FPropertyParamsBase* const PropPointers[];
	static UObject* (*const DependentSingletons[])();
	static constexpr FCppClassTypeInfoStatic StaticCppClassTypeInfo = {
		TCppClassTypeTraits<UTutorialStateSettings>::IsAbstract,
	};
	static const UECodeGen_Private::FClassParams ClassParams;
};
const UECodeGen_Private::FStructPropertyParams Z_Construct_UClass_UTutorialStateSettings_Statics::NewProp_TutorialsProgress_Inner = { "TutorialsProgress", nullptr, (EPropertyFlags)0x0000000000004000, UECodeGen_Private::EPropertyGenFlags::Struct, RF_Public|RF_Transient|RF_MarkAsNative, nullptr, nullptr, 1, 0, Z_Construct_UScriptStruct_FTutorialProgress, METADATA_PARAMS(0, nullptr) }; // 2604388623
const UECodeGen_Private::FArrayPropertyParams Z_Construct_UClass_UTutorialStateSettings_Statics::NewProp_TutorialsProgress = { "TutorialsProgress", nullptr, (EPropertyFlags)0x0010000000004000, UECodeGen_Private::EPropertyGenFlags::Array, RF_Public|RF_Transient|RF_MarkAsNative, nullptr, nullptr, 1, STRUCT_OFFSET(UTutorialStateSettings, TutorialsProgress), EArrayPropertyFlags::None, METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_TutorialsProgress_MetaData), NewProp_TutorialsProgress_MetaData) }; // 2604388623
void Z_Construct_UClass_UTutorialStateSettings_Statics::NewProp_bDismissedAllTutorials_SetBit(void* Obj)
{
	((UTutorialStateSettings*)Obj)->bDismissedAllTutorials = 1;
}
const UECodeGen_Private::FBoolPropertyParams Z_Construct_UClass_UTutorialStateSettings_Statics::NewProp_bDismissedAllTutorials = { "bDismissedAllTutorials", nullptr, (EPropertyFlags)0x0040000000004000, UECodeGen_Private::EPropertyGenFlags::Bool | UECodeGen_Private::EPropertyGenFlags::NativeBool, RF_Public|RF_Transient|RF_MarkAsNative, nullptr, nullptr, 1, sizeof(bool), sizeof(UTutorialStateSettings), &Z_Construct_UClass_UTutorialStateSettings_Statics::NewProp_bDismissedAllTutorials_SetBit, METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_bDismissedAllTutorials_MetaData), NewProp_bDismissedAllTutorials_MetaData) };
const UECodeGen_Private::FPropertyParamsBase* const Z_Construct_UClass_UTutorialStateSettings_Statics::PropPointers[] = {
	(const UECodeGen_Private::FPropertyParamsBase*)&Z_Construct_UClass_UTutorialStateSettings_Statics::NewProp_TutorialsProgress_Inner,
	(const UECodeGen_Private::FPropertyParamsBase*)&Z_Construct_UClass_UTutorialStateSettings_Statics::NewProp_TutorialsProgress,
	(const UECodeGen_Private::FPropertyParamsBase*)&Z_Construct_UClass_UTutorialStateSettings_Statics::NewProp_bDismissedAllTutorials,
};
static_assert(UE_ARRAY_COUNT(Z_Construct_UClass_UTutorialStateSettings_Statics::PropPointers) < 2048);
UObject* (*const Z_Construct_UClass_UTutorialStateSettings_Statics::DependentSingletons[])() = {
	(UObject* (*)())Z_Construct_UClass_UObject,
	(UObject* (*)())Z_Construct_UPackage__Script_IntroTutorials,
};
static_assert(UE_ARRAY_COUNT(Z_Construct_UClass_UTutorialStateSettings_Statics::DependentSingletons) < 16);
const UECodeGen_Private::FClassParams Z_Construct_UClass_UTutorialStateSettings_Statics::ClassParams = {
	&UTutorialStateSettings::StaticClass,
	"EditorSettings",
	&StaticCppClassTypeInfo,
	DependentSingletons,
	nullptr,
	Z_Construct_UClass_UTutorialStateSettings_Statics::PropPointers,
	nullptr,
	UE_ARRAY_COUNT(DependentSingletons),
	0,
	UE_ARRAY_COUNT(Z_Construct_UClass_UTutorialStateSettings_Statics::PropPointers),
	0,
	0x000000A4u,
	METADATA_PARAMS(UE_ARRAY_COUNT(Z_Construct_UClass_UTutorialStateSettings_Statics::Class_MetaDataParams), Z_Construct_UClass_UTutorialStateSettings_Statics::Class_MetaDataParams)
};
UClass* Z_Construct_UClass_UTutorialStateSettings()
{
	if (!Z_Registration_Info_UClass_UTutorialStateSettings.OuterSingleton)
	{
		UECodeGen_Private::ConstructUClass(Z_Registration_Info_UClass_UTutorialStateSettings.OuterSingleton, Z_Construct_UClass_UTutorialStateSettings_Statics::ClassParams);
	}
	return Z_Registration_Info_UClass_UTutorialStateSettings.OuterSingleton;
}
template<> INTROTUTORIALS_API UClass* StaticClass<UTutorialStateSettings>()
{
	return UTutorialStateSettings::StaticClass();
}
DEFINE_VTABLE_PTR_HELPER_CTOR(UTutorialStateSettings);
UTutorialStateSettings::~UTutorialStateSettings() {}
// End Class UTutorialStateSettings

// Begin Registration
struct Z_CompiledInDeferFile_FID_Mineprep_last_0_4_Plugins_GuidedTutorials_Source_IntroTutorials_Private_TutorialStateSettings_h_Statics
{
	static constexpr FStructRegisterCompiledInInfo ScriptStructInfo[] = {
		{ FTutorialProgress::StaticStruct, Z_Construct_UScriptStruct_FTutorialProgress_Statics::NewStructOps, TEXT("TutorialProgress"), &Z_Registration_Info_UScriptStruct_TutorialProgress, CONSTRUCT_RELOAD_VERSION_INFO(FStructReloadVersionInfo, sizeof(FTutorialProgress), 2604388623U) },
	};
	static constexpr FClassRegisterCompiledInInfo ClassInfo[] = {
		{ Z_Construct_UClass_UTutorialStateSettings, UTutorialStateSettings::StaticClass, TEXT("UTutorialStateSettings"), &Z_Registration_Info_UClass_UTutorialStateSettings, CONSTRUCT_RELOAD_VERSION_INFO(FClassReloadVersionInfo, sizeof(UTutorialStateSettings), 4113685746U) },
	};
};
static FRegisterCompiledInInfo Z_CompiledInDeferFile_FID_Mineprep_last_0_4_Plugins_GuidedTutorials_Source_IntroTutorials_Private_TutorialStateSettings_h_806850108(TEXT("/Script/IntroTutorials"),
	Z_CompiledInDeferFile_FID_Mineprep_last_0_4_Plugins_GuidedTutorials_Source_IntroTutorials_Private_TutorialStateSettings_h_Statics::ClassInfo, UE_ARRAY_COUNT(Z_CompiledInDeferFile_FID_Mineprep_last_0_4_Plugins_GuidedTutorials_Source_IntroTutorials_Private_TutorialStateSettings_h_Statics::ClassInfo),
	Z_CompiledInDeferFile_FID_Mineprep_last_0_4_Plugins_GuidedTutorials_Source_IntroTutorials_Private_TutorialStateSettings_h_Statics::ScriptStructInfo, UE_ARRAY_COUNT(Z_CompiledInDeferFile_FID_Mineprep_last_0_4_Plugins_GuidedTutorials_Source_IntroTutorials_Private_TutorialStateSettings_h_Statics::ScriptStructInfo),
	nullptr, 0);
// End Registration
PRAGMA_ENABLE_DEPRECATION_WARNINGS
