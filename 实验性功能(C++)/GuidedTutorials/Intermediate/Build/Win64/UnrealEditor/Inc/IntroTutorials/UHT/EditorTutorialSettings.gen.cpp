// Copyright Epic Games, Inc. All Rights Reserved.
/*===========================================================================
	Generated code exported from UnrealHeaderTool.
	DO NOT modify this manually! Edit the corresponding .h files instead!
===========================================================================*/

#include "UObject/GeneratedCppIncludes.h"
#include "IntroTutorials/Private/EditorTutorialSettings.h"
#include "IntroTutorials/Public/EditorTutorial.h"
PRAGMA_DISABLE_DEPRECATION_WARNINGS
void EmptyLinkFunctionForGeneratedCodeEditorTutorialSettings() {}

// Begin Cross Module References
COREUOBJECT_API UClass* Z_Construct_UClass_UObject();
COREUOBJECT_API UScriptStruct* Z_Construct_UScriptStruct_FSoftClassPath();
INTROTUTORIALS_API UClass* Z_Construct_UClass_UEditorTutorialSettings();
INTROTUTORIALS_API UClass* Z_Construct_UClass_UEditorTutorialSettings_NoRegister();
INTROTUTORIALS_API UScriptStruct* Z_Construct_UScriptStruct_FTutorialCategory();
INTROTUTORIALS_API UScriptStruct* Z_Construct_UScriptStruct_FTutorialContext();
UPackage* Z_Construct_UPackage__Script_IntroTutorials();
// End Cross Module References

// Begin ScriptStruct FTutorialContext
static FStructRegistrationInfo Z_Registration_Info_UScriptStruct_TutorialContext;
class UScriptStruct* FTutorialContext::StaticStruct()
{
	if (!Z_Registration_Info_UScriptStruct_TutorialContext.OuterSingleton)
	{
		Z_Registration_Info_UScriptStruct_TutorialContext.OuterSingleton = GetStaticStruct(Z_Construct_UScriptStruct_FTutorialContext, (UObject*)Z_Construct_UPackage__Script_IntroTutorials(), TEXT("TutorialContext"));
	}
	return Z_Registration_Info_UScriptStruct_TutorialContext.OuterSingleton;
}
template<> INTROTUTORIALS_API UScriptStruct* StaticStruct<FTutorialContext>()
{
	return FTutorialContext::StaticStruct();
}
struct Z_Construct_UScriptStruct_FTutorialContext_Statics
{
#if WITH_METADATA
	static constexpr UECodeGen_Private::FMetaDataPairParam Struct_MetaDataParams[] = {
#if !UE_BUILD_SHIPPING
		{ "Comment", "/** Named context that corresponds to a particular tutorial */" },
#endif
		{ "ModuleRelativePath", "Private/EditorTutorialSettings.h" },
#if !UE_BUILD_SHIPPING
		{ "ToolTip", "Named context that corresponds to a particular tutorial" },
#endif
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_Context_MetaData[] = {
		{ "Category", "Tutorials" },
#if !UE_BUILD_SHIPPING
		{ "Comment", "/** The context that this tutorial is used in */" },
#endif
		{ "ModuleRelativePath", "Private/EditorTutorialSettings.h" },
#if !UE_BUILD_SHIPPING
		{ "ToolTip", "The context that this tutorial is used in" },
#endif
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_BrowserFilter_MetaData[] = {
		{ "Category", "Tutorials" },
#if !UE_BUILD_SHIPPING
		{ "Comment", "/** The filter string to apply to the tutorials browser when launched from this context */" },
#endif
		{ "ModuleRelativePath", "Private/EditorTutorialSettings.h" },
#if !UE_BUILD_SHIPPING
		{ "ToolTip", "The filter string to apply to the tutorials browser when launched from this context" },
#endif
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_AttractTutorial_MetaData[] = {
		{ "Category", "Tutorials" },
#if !UE_BUILD_SHIPPING
		{ "Comment", "/** The tutorial to use in this context to let the user know there is a tutorial available */" },
#endif
		{ "MetaClass", "/Script/IntroTutorials.EditorTutorial" },
		{ "ModuleRelativePath", "Private/EditorTutorialSettings.h" },
#if !UE_BUILD_SHIPPING
		{ "ToolTip", "The tutorial to use in this context to let the user know there is a tutorial available" },
#endif
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_LaunchTutorial_MetaData[] = {
		{ "Category", "Tutorials" },
#if !UE_BUILD_SHIPPING
		{ "Comment", "/** The tutorial to use in this context when the user chooses to launch */" },
#endif
		{ "MetaClass", "/Script/IntroTutorials.EditorTutorial" },
		{ "ModuleRelativePath", "Private/EditorTutorialSettings.h" },
#if !UE_BUILD_SHIPPING
		{ "ToolTip", "The tutorial to use in this context when the user chooses to launch" },
#endif
	};
#endif // WITH_METADATA
	static const UECodeGen_Private::FNamePropertyParams NewProp_Context;
	static const UECodeGen_Private::FStrPropertyParams NewProp_BrowserFilter;
	static const UECodeGen_Private::FStructPropertyParams NewProp_AttractTutorial;
	static const UECodeGen_Private::FStructPropertyParams NewProp_LaunchTutorial;
	static const UECodeGen_Private::FPropertyParamsBase* const PropPointers[];
	static void* NewStructOps()
	{
		return (UScriptStruct::ICppStructOps*)new UScriptStruct::TCppStructOps<FTutorialContext>();
	}
	static const UECodeGen_Private::FStructParams StructParams;
};
const UECodeGen_Private::FNamePropertyParams Z_Construct_UScriptStruct_FTutorialContext_Statics::NewProp_Context = { "Context", nullptr, (EPropertyFlags)0x0010000000000001, UECodeGen_Private::EPropertyGenFlags::Name, RF_Public|RF_Transient|RF_MarkAsNative, nullptr, nullptr, 1, STRUCT_OFFSET(FTutorialContext, Context), METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_Context_MetaData), NewProp_Context_MetaData) };
const UECodeGen_Private::FStrPropertyParams Z_Construct_UScriptStruct_FTutorialContext_Statics::NewProp_BrowserFilter = { "BrowserFilter", nullptr, (EPropertyFlags)0x0010000000000001, UECodeGen_Private::EPropertyGenFlags::Str, RF_Public|RF_Transient|RF_MarkAsNative, nullptr, nullptr, 1, STRUCT_OFFSET(FTutorialContext, BrowserFilter), METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_BrowserFilter_MetaData), NewProp_BrowserFilter_MetaData) };
const UECodeGen_Private::FStructPropertyParams Z_Construct_UScriptStruct_FTutorialContext_Statics::NewProp_AttractTutorial = { "AttractTutorial", nullptr, (EPropertyFlags)0x0010000000000001, UECodeGen_Private::EPropertyGenFlags::Struct, RF_Public|RF_Transient|RF_MarkAsNative, nullptr, nullptr, 1, STRUCT_OFFSET(FTutorialContext, AttractTutorial), Z_Construct_UScriptStruct_FSoftClassPath, METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_AttractTutorial_MetaData), NewProp_AttractTutorial_MetaData) };
const UECodeGen_Private::FStructPropertyParams Z_Construct_UScriptStruct_FTutorialContext_Statics::NewProp_LaunchTutorial = { "LaunchTutorial", nullptr, (EPropertyFlags)0x0010000000000001, UECodeGen_Private::EPropertyGenFlags::Struct, RF_Public|RF_Transient|RF_MarkAsNative, nullptr, nullptr, 1, STRUCT_OFFSET(FTutorialContext, LaunchTutorial), Z_Construct_UScriptStruct_FSoftClassPath, METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_LaunchTutorial_MetaData), NewProp_LaunchTutorial_MetaData) };
const UECodeGen_Private::FPropertyParamsBase* const Z_Construct_UScriptStruct_FTutorialContext_Statics::PropPointers[] = {
	(const UECodeGen_Private::FPropertyParamsBase*)&Z_Construct_UScriptStruct_FTutorialContext_Statics::NewProp_Context,
	(const UECodeGen_Private::FPropertyParamsBase*)&Z_Construct_UScriptStruct_FTutorialContext_Statics::NewProp_BrowserFilter,
	(const UECodeGen_Private::FPropertyParamsBase*)&Z_Construct_UScriptStruct_FTutorialContext_Statics::NewProp_AttractTutorial,
	(const UECodeGen_Private::FPropertyParamsBase*)&Z_Construct_UScriptStruct_FTutorialContext_Statics::NewProp_LaunchTutorial,
};
static_assert(UE_ARRAY_COUNT(Z_Construct_UScriptStruct_FTutorialContext_Statics::PropPointers) < 2048);
const UECodeGen_Private::FStructParams Z_Construct_UScriptStruct_FTutorialContext_Statics::StructParams = {
	(UObject* (*)())Z_Construct_UPackage__Script_IntroTutorials,
	nullptr,
	&NewStructOps,
	"TutorialContext",
	Z_Construct_UScriptStruct_FTutorialContext_Statics::PropPointers,
	UE_ARRAY_COUNT(Z_Construct_UScriptStruct_FTutorialContext_Statics::PropPointers),
	sizeof(FTutorialContext),
	alignof(FTutorialContext),
	RF_Public|RF_Transient|RF_MarkAsNative,
	EStructFlags(0x00000001),
	METADATA_PARAMS(UE_ARRAY_COUNT(Z_Construct_UScriptStruct_FTutorialContext_Statics::Struct_MetaDataParams), Z_Construct_UScriptStruct_FTutorialContext_Statics::Struct_MetaDataParams)
};
UScriptStruct* Z_Construct_UScriptStruct_FTutorialContext()
{
	if (!Z_Registration_Info_UScriptStruct_TutorialContext.InnerSingleton)
	{
		UECodeGen_Private::ConstructUScriptStruct(Z_Registration_Info_UScriptStruct_TutorialContext.InnerSingleton, Z_Construct_UScriptStruct_FTutorialContext_Statics::StructParams);
	}
	return Z_Registration_Info_UScriptStruct_TutorialContext.InnerSingleton;
}
// End ScriptStruct FTutorialContext

// Begin Class UEditorTutorialSettings
void UEditorTutorialSettings::StaticRegisterNativesUEditorTutorialSettings()
{
}
IMPLEMENT_CLASS_NO_AUTO_REGISTRATION(UEditorTutorialSettings);
UClass* Z_Construct_UClass_UEditorTutorialSettings_NoRegister()
{
	return UEditorTutorialSettings::StaticClass();
}
struct Z_Construct_UClass_UEditorTutorialSettings_Statics
{
#if WITH_METADATA
	static constexpr UECodeGen_Private::FMetaDataPairParam Class_MetaDataParams[] = {
#if !UE_BUILD_SHIPPING
		{ "Comment", "/** Editor-wide tutorial settings */" },
#endif
		{ "IncludePath", "EditorTutorialSettings.h" },
		{ "ModuleRelativePath", "Private/EditorTutorialSettings.h" },
#if !UE_BUILD_SHIPPING
		{ "ToolTip", "Editor-wide tutorial settings" },
#endif
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_bDisableAllTutorialAlerts_MetaData[] = {
		{ "Category", "Tutorials" },
#if !UE_BUILD_SHIPPING
		{ "Comment", "/** Disable the pulsing alert that indicates a new tutorial is available. */" },
#endif
		{ "ModuleRelativePath", "Private/EditorTutorialSettings.h" },
#if !UE_BUILD_SHIPPING
		{ "ToolTip", "Disable the pulsing alert that indicates a new tutorial is available." },
#endif
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_Categories_MetaData[] = {
		{ "Category", "Tutorials" },
#if !UE_BUILD_SHIPPING
		{ "Comment", "/** Categories for tutorials */" },
#endif
		{ "ModuleRelativePath", "Private/EditorTutorialSettings.h" },
#if !UE_BUILD_SHIPPING
		{ "ToolTip", "Categories for tutorials" },
#endif
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_StartupTutorial_MetaData[] = {
		{ "Category", "Tutorials" },
#if !UE_BUILD_SHIPPING
		{ "Comment", "/** Tutorial to start on Editor startup */" },
#endif
		{ "MetaClass", "/Script/IntroTutorials.EditorTutorial" },
		{ "ModuleRelativePath", "Private/EditorTutorialSettings.h" },
#if !UE_BUILD_SHIPPING
		{ "ToolTip", "Tutorial to start on Editor startup" },
#endif
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_TutorialContexts_MetaData[] = {
		{ "Category", "Tutorials" },
#if !UE_BUILD_SHIPPING
		{ "Comment", "/** Tutorials used in various contexts - e.g. the various asset editors */" },
#endif
		{ "ModuleRelativePath", "Private/EditorTutorialSettings.h" },
#if !UE_BUILD_SHIPPING
		{ "ToolTip", "Tutorials used in various contexts - e.g. the various asset editors" },
#endif
	};
#endif // WITH_METADATA
	static void NewProp_bDisableAllTutorialAlerts_SetBit(void* Obj);
	static const UECodeGen_Private::FBoolPropertyParams NewProp_bDisableAllTutorialAlerts;
	static const UECodeGen_Private::FStructPropertyParams NewProp_Categories_Inner;
	static const UECodeGen_Private::FArrayPropertyParams NewProp_Categories;
	static const UECodeGen_Private::FStructPropertyParams NewProp_StartupTutorial;
	static const UECodeGen_Private::FStructPropertyParams NewProp_TutorialContexts_Inner;
	static const UECodeGen_Private::FArrayPropertyParams NewProp_TutorialContexts;
	static const UECodeGen_Private::FPropertyParamsBase* const PropPointers[];
	static UObject* (*const DependentSingletons[])();
	static constexpr FCppClassTypeInfoStatic StaticCppClassTypeInfo = {
		TCppClassTypeTraits<UEditorTutorialSettings>::IsAbstract,
	};
	static const UECodeGen_Private::FClassParams ClassParams;
};
void Z_Construct_UClass_UEditorTutorialSettings_Statics::NewProp_bDisableAllTutorialAlerts_SetBit(void* Obj)
{
	((UEditorTutorialSettings*)Obj)->bDisableAllTutorialAlerts = 1;
}
const UECodeGen_Private::FBoolPropertyParams Z_Construct_UClass_UEditorTutorialSettings_Statics::NewProp_bDisableAllTutorialAlerts = { "bDisableAllTutorialAlerts", nullptr, (EPropertyFlags)0x0010000000004001, UECodeGen_Private::EPropertyGenFlags::Bool | UECodeGen_Private::EPropertyGenFlags::NativeBool, RF_Public|RF_Transient|RF_MarkAsNative, nullptr, nullptr, 1, sizeof(bool), sizeof(UEditorTutorialSettings), &Z_Construct_UClass_UEditorTutorialSettings_Statics::NewProp_bDisableAllTutorialAlerts_SetBit, METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_bDisableAllTutorialAlerts_MetaData), NewProp_bDisableAllTutorialAlerts_MetaData) };
const UECodeGen_Private::FStructPropertyParams Z_Construct_UClass_UEditorTutorialSettings_Statics::NewProp_Categories_Inner = { "Categories", nullptr, (EPropertyFlags)0x0000000000004000, UECodeGen_Private::EPropertyGenFlags::Struct, RF_Public|RF_Transient|RF_MarkAsNative, nullptr, nullptr, 1, 0, Z_Construct_UScriptStruct_FTutorialCategory, METADATA_PARAMS(0, nullptr) }; // 3911846307
const UECodeGen_Private::FArrayPropertyParams Z_Construct_UClass_UEditorTutorialSettings_Statics::NewProp_Categories = { "Categories", nullptr, (EPropertyFlags)0x0010000000004001, UECodeGen_Private::EPropertyGenFlags::Array, RF_Public|RF_Transient|RF_MarkAsNative, nullptr, nullptr, 1, STRUCT_OFFSET(UEditorTutorialSettings, Categories), EArrayPropertyFlags::None, METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_Categories_MetaData), NewProp_Categories_MetaData) }; // 3911846307
const UECodeGen_Private::FStructPropertyParams Z_Construct_UClass_UEditorTutorialSettings_Statics::NewProp_StartupTutorial = { "StartupTutorial", nullptr, (EPropertyFlags)0x0010000000004001, UECodeGen_Private::EPropertyGenFlags::Struct, RF_Public|RF_Transient|RF_MarkAsNative, nullptr, nullptr, 1, STRUCT_OFFSET(UEditorTutorialSettings, StartupTutorial), Z_Construct_UScriptStruct_FSoftClassPath, METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_StartupTutorial_MetaData), NewProp_StartupTutorial_MetaData) };
const UECodeGen_Private::FStructPropertyParams Z_Construct_UClass_UEditorTutorialSettings_Statics::NewProp_TutorialContexts_Inner = { "TutorialContexts", nullptr, (EPropertyFlags)0x0000000000004000, UECodeGen_Private::EPropertyGenFlags::Struct, RF_Public|RF_Transient|RF_MarkAsNative, nullptr, nullptr, 1, 0, Z_Construct_UScriptStruct_FTutorialContext, METADATA_PARAMS(0, nullptr) }; // 140600580
const UECodeGen_Private::FArrayPropertyParams Z_Construct_UClass_UEditorTutorialSettings_Statics::NewProp_TutorialContexts = { "TutorialContexts", nullptr, (EPropertyFlags)0x0010000000004001, UECodeGen_Private::EPropertyGenFlags::Array, RF_Public|RF_Transient|RF_MarkAsNative, nullptr, nullptr, 1, STRUCT_OFFSET(UEditorTutorialSettings, TutorialContexts), EArrayPropertyFlags::None, METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_TutorialContexts_MetaData), NewProp_TutorialContexts_MetaData) }; // 140600580
const UECodeGen_Private::FPropertyParamsBase* const Z_Construct_UClass_UEditorTutorialSettings_Statics::PropPointers[] = {
	(const UECodeGen_Private::FPropertyParamsBase*)&Z_Construct_UClass_UEditorTutorialSettings_Statics::NewProp_bDisableAllTutorialAlerts,
	(const UECodeGen_Private::FPropertyParamsBase*)&Z_Construct_UClass_UEditorTutorialSettings_Statics::NewProp_Categories_Inner,
	(const UECodeGen_Private::FPropertyParamsBase*)&Z_Construct_UClass_UEditorTutorialSettings_Statics::NewProp_Categories,
	(const UECodeGen_Private::FPropertyParamsBase*)&Z_Construct_UClass_UEditorTutorialSettings_Statics::NewProp_StartupTutorial,
	(const UECodeGen_Private::FPropertyParamsBase*)&Z_Construct_UClass_UEditorTutorialSettings_Statics::NewProp_TutorialContexts_Inner,
	(const UECodeGen_Private::FPropertyParamsBase*)&Z_Construct_UClass_UEditorTutorialSettings_Statics::NewProp_TutorialContexts,
};
static_assert(UE_ARRAY_COUNT(Z_Construct_UClass_UEditorTutorialSettings_Statics::PropPointers) < 2048);
UObject* (*const Z_Construct_UClass_UEditorTutorialSettings_Statics::DependentSingletons[])() = {
	(UObject* (*)())Z_Construct_UClass_UObject,
	(UObject* (*)())Z_Construct_UPackage__Script_IntroTutorials,
};
static_assert(UE_ARRAY_COUNT(Z_Construct_UClass_UEditorTutorialSettings_Statics::DependentSingletons) < 16);
const UECodeGen_Private::FClassParams Z_Construct_UClass_UEditorTutorialSettings_Statics::ClassParams = {
	&UEditorTutorialSettings::StaticClass,
	"GuidedTutorials",
	&StaticCppClassTypeInfo,
	DependentSingletons,
	nullptr,
	Z_Construct_UClass_UEditorTutorialSettings_Statics::PropPointers,
	nullptr,
	UE_ARRAY_COUNT(DependentSingletons),
	0,
	UE_ARRAY_COUNT(Z_Construct_UClass_UEditorTutorialSettings_Statics::PropPointers),
	0,
	0x000000A4u,
	METADATA_PARAMS(UE_ARRAY_COUNT(Z_Construct_UClass_UEditorTutorialSettings_Statics::Class_MetaDataParams), Z_Construct_UClass_UEditorTutorialSettings_Statics::Class_MetaDataParams)
};
UClass* Z_Construct_UClass_UEditorTutorialSettings()
{
	if (!Z_Registration_Info_UClass_UEditorTutorialSettings.OuterSingleton)
	{
		UECodeGen_Private::ConstructUClass(Z_Registration_Info_UClass_UEditorTutorialSettings.OuterSingleton, Z_Construct_UClass_UEditorTutorialSettings_Statics::ClassParams);
	}
	return Z_Registration_Info_UClass_UEditorTutorialSettings.OuterSingleton;
}
template<> INTROTUTORIALS_API UClass* StaticClass<UEditorTutorialSettings>()
{
	return UEditorTutorialSettings::StaticClass();
}
DEFINE_VTABLE_PTR_HELPER_CTOR(UEditorTutorialSettings);
UEditorTutorialSettings::~UEditorTutorialSettings() {}
// End Class UEditorTutorialSettings

// Begin Registration
struct Z_CompiledInDeferFile_FID_Mineprep_last_0_4_Plugins_GuidedTutorials_Source_IntroTutorials_Private_EditorTutorialSettings_h_Statics
{
	static constexpr FStructRegisterCompiledInInfo ScriptStructInfo[] = {
		{ FTutorialContext::StaticStruct, Z_Construct_UScriptStruct_FTutorialContext_Statics::NewStructOps, TEXT("TutorialContext"), &Z_Registration_Info_UScriptStruct_TutorialContext, CONSTRUCT_RELOAD_VERSION_INFO(FStructReloadVersionInfo, sizeof(FTutorialContext), 140600580U) },
	};
	static constexpr FClassRegisterCompiledInInfo ClassInfo[] = {
		{ Z_Construct_UClass_UEditorTutorialSettings, UEditorTutorialSettings::StaticClass, TEXT("UEditorTutorialSettings"), &Z_Registration_Info_UClass_UEditorTutorialSettings, CONSTRUCT_RELOAD_VERSION_INFO(FClassReloadVersionInfo, sizeof(UEditorTutorialSettings), 1174063818U) },
	};
};
static FRegisterCompiledInInfo Z_CompiledInDeferFile_FID_Mineprep_last_0_4_Plugins_GuidedTutorials_Source_IntroTutorials_Private_EditorTutorialSettings_h_1958227859(TEXT("/Script/IntroTutorials"),
	Z_CompiledInDeferFile_FID_Mineprep_last_0_4_Plugins_GuidedTutorials_Source_IntroTutorials_Private_EditorTutorialSettings_h_Statics::ClassInfo, UE_ARRAY_COUNT(Z_CompiledInDeferFile_FID_Mineprep_last_0_4_Plugins_GuidedTutorials_Source_IntroTutorials_Private_EditorTutorialSettings_h_Statics::ClassInfo),
	Z_CompiledInDeferFile_FID_Mineprep_last_0_4_Plugins_GuidedTutorials_Source_IntroTutorials_Private_EditorTutorialSettings_h_Statics::ScriptStructInfo, UE_ARRAY_COUNT(Z_CompiledInDeferFile_FID_Mineprep_last_0_4_Plugins_GuidedTutorials_Source_IntroTutorials_Private_EditorTutorialSettings_h_Statics::ScriptStructInfo),
	nullptr, 0);
// End Registration
PRAGMA_ENABLE_DEPRECATION_WARNINGS
