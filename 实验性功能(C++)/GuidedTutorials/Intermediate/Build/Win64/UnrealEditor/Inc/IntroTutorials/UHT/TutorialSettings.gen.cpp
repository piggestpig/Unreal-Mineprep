// Copyright Epic Games, Inc. All Rights Reserved.
/*===========================================================================
	Generated code exported from UnrealHeaderTool.
	DO NOT modify this manually! Edit the corresponding .h files instead!
===========================================================================*/

#include "UObject/GeneratedCppIncludes.h"
#include "IntroTutorials/Private/TutorialSettings.h"
#include "IntroTutorials/Public/EditorTutorial.h"
PRAGMA_DISABLE_DEPRECATION_WARNINGS
void EmptyLinkFunctionForGeneratedCodeTutorialSettings() {}

// Begin Cross Module References
COREUOBJECT_API UClass* Z_Construct_UClass_UObject();
COREUOBJECT_API UScriptStruct* Z_Construct_UScriptStruct_FSoftClassPath();
INTROTUTORIALS_API UClass* Z_Construct_UClass_UTutorialSettings();
INTROTUTORIALS_API UClass* Z_Construct_UClass_UTutorialSettings_NoRegister();
INTROTUTORIALS_API UScriptStruct* Z_Construct_UScriptStruct_FTutorialCategory();
UPackage* Z_Construct_UPackage__Script_IntroTutorials();
// End Cross Module References

// Begin Class UTutorialSettings
void UTutorialSettings::StaticRegisterNativesUTutorialSettings()
{
}
IMPLEMENT_CLASS_NO_AUTO_REGISTRATION(UTutorialSettings);
UClass* Z_Construct_UClass_UTutorialSettings_NoRegister()
{
	return UTutorialSettings::StaticClass();
}
struct Z_Construct_UClass_UTutorialSettings_Statics
{
#if WITH_METADATA
	static constexpr UECodeGen_Private::FMetaDataPairParam Class_MetaDataParams[] = {
#if !UE_BUILD_SHIPPING
		{ "Comment", "/** Per-project tutorial settings */" },
#endif
		{ "IncludePath", "TutorialSettings.h" },
		{ "ModuleRelativePath", "Private/TutorialSettings.h" },
#if !UE_BUILD_SHIPPING
		{ "ToolTip", "Per-project tutorial settings" },
#endif
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_Categories_MetaData[] = {
		{ "Category", "Tutorials" },
#if !UE_BUILD_SHIPPING
		{ "Comment", "/** Categories for tutorials */" },
#endif
		{ "ModuleRelativePath", "Private/TutorialSettings.h" },
#if !UE_BUILD_SHIPPING
		{ "ToolTip", "Categories for tutorials" },
#endif
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_StartupTutorial_MetaData[] = {
		{ "Category", "Tutorials" },
#if !UE_BUILD_SHIPPING
		{ "Comment", "/** Tutorial to start on project startup */" },
#endif
		{ "MetaClass", "/Script/IntroTutorials.EditorTutorial" },
		{ "ModuleRelativePath", "Private/TutorialSettings.h" },
#if !UE_BUILD_SHIPPING
		{ "ToolTip", "Tutorial to start on project startup" },
#endif
	};
#endif // WITH_METADATA
	static const UECodeGen_Private::FStructPropertyParams NewProp_Categories_Inner;
	static const UECodeGen_Private::FArrayPropertyParams NewProp_Categories;
	static const UECodeGen_Private::FStructPropertyParams NewProp_StartupTutorial;
	static const UECodeGen_Private::FPropertyParamsBase* const PropPointers[];
	static UObject* (*const DependentSingletons[])();
	static constexpr FCppClassTypeInfoStatic StaticCppClassTypeInfo = {
		TCppClassTypeTraits<UTutorialSettings>::IsAbstract,
	};
	static const UECodeGen_Private::FClassParams ClassParams;
};
const UECodeGen_Private::FStructPropertyParams Z_Construct_UClass_UTutorialSettings_Statics::NewProp_Categories_Inner = { "Categories", nullptr, (EPropertyFlags)0x0000000000004000, UECodeGen_Private::EPropertyGenFlags::Struct, RF_Public|RF_Transient|RF_MarkAsNative, nullptr, nullptr, 1, 0, Z_Construct_UScriptStruct_FTutorialCategory, METADATA_PARAMS(0, nullptr) }; // 3911846307
const UECodeGen_Private::FArrayPropertyParams Z_Construct_UClass_UTutorialSettings_Statics::NewProp_Categories = { "Categories", nullptr, (EPropertyFlags)0x0010000000004001, UECodeGen_Private::EPropertyGenFlags::Array, RF_Public|RF_Transient|RF_MarkAsNative, nullptr, nullptr, 1, STRUCT_OFFSET(UTutorialSettings, Categories), EArrayPropertyFlags::None, METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_Categories_MetaData), NewProp_Categories_MetaData) }; // 3911846307
const UECodeGen_Private::FStructPropertyParams Z_Construct_UClass_UTutorialSettings_Statics::NewProp_StartupTutorial = { "StartupTutorial", nullptr, (EPropertyFlags)0x0010000000004001, UECodeGen_Private::EPropertyGenFlags::Struct, RF_Public|RF_Transient|RF_MarkAsNative, nullptr, nullptr, 1, STRUCT_OFFSET(UTutorialSettings, StartupTutorial), Z_Construct_UScriptStruct_FSoftClassPath, METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_StartupTutorial_MetaData), NewProp_StartupTutorial_MetaData) };
const UECodeGen_Private::FPropertyParamsBase* const Z_Construct_UClass_UTutorialSettings_Statics::PropPointers[] = {
	(const UECodeGen_Private::FPropertyParamsBase*)&Z_Construct_UClass_UTutorialSettings_Statics::NewProp_Categories_Inner,
	(const UECodeGen_Private::FPropertyParamsBase*)&Z_Construct_UClass_UTutorialSettings_Statics::NewProp_Categories,
	(const UECodeGen_Private::FPropertyParamsBase*)&Z_Construct_UClass_UTutorialSettings_Statics::NewProp_StartupTutorial,
};
static_assert(UE_ARRAY_COUNT(Z_Construct_UClass_UTutorialSettings_Statics::PropPointers) < 2048);
UObject* (*const Z_Construct_UClass_UTutorialSettings_Statics::DependentSingletons[])() = {
	(UObject* (*)())Z_Construct_UClass_UObject,
	(UObject* (*)())Z_Construct_UPackage__Script_IntroTutorials,
};
static_assert(UE_ARRAY_COUNT(Z_Construct_UClass_UTutorialSettings_Statics::DependentSingletons) < 16);
const UECodeGen_Private::FClassParams Z_Construct_UClass_UTutorialSettings_Statics::ClassParams = {
	&UTutorialSettings::StaticClass,
	"Editor",
	&StaticCppClassTypeInfo,
	DependentSingletons,
	nullptr,
	Z_Construct_UClass_UTutorialSettings_Statics::PropPointers,
	nullptr,
	UE_ARRAY_COUNT(DependentSingletons),
	0,
	UE_ARRAY_COUNT(Z_Construct_UClass_UTutorialSettings_Statics::PropPointers),
	0,
	0x000000A4u,
	METADATA_PARAMS(UE_ARRAY_COUNT(Z_Construct_UClass_UTutorialSettings_Statics::Class_MetaDataParams), Z_Construct_UClass_UTutorialSettings_Statics::Class_MetaDataParams)
};
UClass* Z_Construct_UClass_UTutorialSettings()
{
	if (!Z_Registration_Info_UClass_UTutorialSettings.OuterSingleton)
	{
		UECodeGen_Private::ConstructUClass(Z_Registration_Info_UClass_UTutorialSettings.OuterSingleton, Z_Construct_UClass_UTutorialSettings_Statics::ClassParams);
	}
	return Z_Registration_Info_UClass_UTutorialSettings.OuterSingleton;
}
template<> INTROTUTORIALS_API UClass* StaticClass<UTutorialSettings>()
{
	return UTutorialSettings::StaticClass();
}
DEFINE_VTABLE_PTR_HELPER_CTOR(UTutorialSettings);
UTutorialSettings::~UTutorialSettings() {}
// End Class UTutorialSettings

// Begin Registration
struct Z_CompiledInDeferFile_FID_Mineprep_last_0_4_Plugins_GuidedTutorials_Source_IntroTutorials_Private_TutorialSettings_h_Statics
{
	static constexpr FClassRegisterCompiledInInfo ClassInfo[] = {
		{ Z_Construct_UClass_UTutorialSettings, UTutorialSettings::StaticClass, TEXT("UTutorialSettings"), &Z_Registration_Info_UClass_UTutorialSettings, CONSTRUCT_RELOAD_VERSION_INFO(FClassReloadVersionInfo, sizeof(UTutorialSettings), 2642615951U) },
	};
};
static FRegisterCompiledInInfo Z_CompiledInDeferFile_FID_Mineprep_last_0_4_Plugins_GuidedTutorials_Source_IntroTutorials_Private_TutorialSettings_h_966168819(TEXT("/Script/IntroTutorials"),
	Z_CompiledInDeferFile_FID_Mineprep_last_0_4_Plugins_GuidedTutorials_Source_IntroTutorials_Private_TutorialSettings_h_Statics::ClassInfo, UE_ARRAY_COUNT(Z_CompiledInDeferFile_FID_Mineprep_last_0_4_Plugins_GuidedTutorials_Source_IntroTutorials_Private_TutorialSettings_h_Statics::ClassInfo),
	nullptr, 0,
	nullptr, 0);
// End Registration
PRAGMA_ENABLE_DEPRECATION_WARNINGS
