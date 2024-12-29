// Copyright Epic Games, Inc. All Rights Reserved.
/*===========================================================================
	Generated code exported from UnrealHeaderTool.
	DO NOT modify this manually! Edit the corresponding .h files instead!
===========================================================================*/

#include "UObject/GeneratedCppIncludes.h"
#include "IntroTutorials/Private/EditorTutorialImportFactory.h"
PRAGMA_DISABLE_DEPRECATION_WARNINGS
void EmptyLinkFunctionForGeneratedCodeEditorTutorialImportFactory() {}

// Begin Cross Module References
INTROTUTORIALS_API UClass* Z_Construct_UClass_UEditorTutorialImportFactory();
INTROTUTORIALS_API UClass* Z_Construct_UClass_UEditorTutorialImportFactory_NoRegister();
UNREALED_API UClass* Z_Construct_UClass_UFactory();
UPackage* Z_Construct_UPackage__Script_IntroTutorials();
// End Cross Module References

// Begin Class UEditorTutorialImportFactory
void UEditorTutorialImportFactory::StaticRegisterNativesUEditorTutorialImportFactory()
{
}
IMPLEMENT_CLASS_NO_AUTO_REGISTRATION(UEditorTutorialImportFactory);
UClass* Z_Construct_UClass_UEditorTutorialImportFactory_NoRegister()
{
	return UEditorTutorialImportFactory::StaticClass();
}
struct Z_Construct_UClass_UEditorTutorialImportFactory_Statics
{
#if WITH_METADATA
	static constexpr UECodeGen_Private::FMetaDataPairParam Class_MetaDataParams[] = {
		{ "HideCategories", "Object" },
		{ "IncludePath", "EditorTutorialImportFactory.h" },
		{ "ModuleRelativePath", "Private/EditorTutorialImportFactory.h" },
	};
#endif // WITH_METADATA
	static UObject* (*const DependentSingletons[])();
	static constexpr FCppClassTypeInfoStatic StaticCppClassTypeInfo = {
		TCppClassTypeTraits<UEditorTutorialImportFactory>::IsAbstract,
	};
	static const UECodeGen_Private::FClassParams ClassParams;
};
UObject* (*const Z_Construct_UClass_UEditorTutorialImportFactory_Statics::DependentSingletons[])() = {
	(UObject* (*)())Z_Construct_UClass_UFactory,
	(UObject* (*)())Z_Construct_UPackage__Script_IntroTutorials,
};
static_assert(UE_ARRAY_COUNT(Z_Construct_UClass_UEditorTutorialImportFactory_Statics::DependentSingletons) < 16);
const UECodeGen_Private::FClassParams Z_Construct_UClass_UEditorTutorialImportFactory_Statics::ClassParams = {
	&UEditorTutorialImportFactory::StaticClass,
	nullptr,
	&StaticCppClassTypeInfo,
	DependentSingletons,
	nullptr,
	nullptr,
	nullptr,
	UE_ARRAY_COUNT(DependentSingletons),
	0,
	0,
	0,
	0x000020A0u,
	METADATA_PARAMS(UE_ARRAY_COUNT(Z_Construct_UClass_UEditorTutorialImportFactory_Statics::Class_MetaDataParams), Z_Construct_UClass_UEditorTutorialImportFactory_Statics::Class_MetaDataParams)
};
UClass* Z_Construct_UClass_UEditorTutorialImportFactory()
{
	if (!Z_Registration_Info_UClass_UEditorTutorialImportFactory.OuterSingleton)
	{
		UECodeGen_Private::ConstructUClass(Z_Registration_Info_UClass_UEditorTutorialImportFactory.OuterSingleton, Z_Construct_UClass_UEditorTutorialImportFactory_Statics::ClassParams);
	}
	return Z_Registration_Info_UClass_UEditorTutorialImportFactory.OuterSingleton;
}
template<> INTROTUTORIALS_API UClass* StaticClass<UEditorTutorialImportFactory>()
{
	return UEditorTutorialImportFactory::StaticClass();
}
DEFINE_VTABLE_PTR_HELPER_CTOR(UEditorTutorialImportFactory);
UEditorTutorialImportFactory::~UEditorTutorialImportFactory() {}
// End Class UEditorTutorialImportFactory

// Begin Registration
struct Z_CompiledInDeferFile_FID_Mineprep_last_0_4_Plugins_GuidedTutorials_Source_IntroTutorials_Private_EditorTutorialImportFactory_h_Statics
{
	static constexpr FClassRegisterCompiledInInfo ClassInfo[] = {
		{ Z_Construct_UClass_UEditorTutorialImportFactory, UEditorTutorialImportFactory::StaticClass, TEXT("UEditorTutorialImportFactory"), &Z_Registration_Info_UClass_UEditorTutorialImportFactory, CONSTRUCT_RELOAD_VERSION_INFO(FClassReloadVersionInfo, sizeof(UEditorTutorialImportFactory), 1795225642U) },
	};
};
static FRegisterCompiledInInfo Z_CompiledInDeferFile_FID_Mineprep_last_0_4_Plugins_GuidedTutorials_Source_IntroTutorials_Private_EditorTutorialImportFactory_h_3209865984(TEXT("/Script/IntroTutorials"),
	Z_CompiledInDeferFile_FID_Mineprep_last_0_4_Plugins_GuidedTutorials_Source_IntroTutorials_Private_EditorTutorialImportFactory_h_Statics::ClassInfo, UE_ARRAY_COUNT(Z_CompiledInDeferFile_FID_Mineprep_last_0_4_Plugins_GuidedTutorials_Source_IntroTutorials_Private_EditorTutorialImportFactory_h_Statics::ClassInfo),
	nullptr, 0,
	nullptr, 0);
// End Registration
PRAGMA_ENABLE_DEPRECATION_WARNINGS
