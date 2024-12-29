// Copyright Epic Games, Inc. All Rights Reserved.
/*===========================================================================
	Generated code exported from UnrealHeaderTool.
	DO NOT modify this manually! Edit the corresponding .h files instead!
===========================================================================*/

// IWYU pragma: private, include "EditorTutorialSettings.h"
#include "UObject/ObjectMacros.h"
#include "UObject/ScriptMacros.h"

PRAGMA_DISABLE_DEPRECATION_WARNINGS
#ifdef INTROTUTORIALS_EditorTutorialSettings_generated_h
#error "EditorTutorialSettings.generated.h already included, missing '#pragma once' in EditorTutorialSettings.h"
#endif
#define INTROTUTORIALS_EditorTutorialSettings_generated_h

#define FID_Mineprep_last_0_4_Plugins_GuidedTutorials_Source_IntroTutorials_Private_EditorTutorialSettings_h_16_GENERATED_BODY \
	friend struct Z_Construct_UScriptStruct_FTutorialContext_Statics; \
	INTROTUTORIALS_API static class UScriptStruct* StaticStruct();


template<> INTROTUTORIALS_API UScriptStruct* StaticStruct<struct FTutorialContext>();

#define FID_Mineprep_last_0_4_Plugins_GuidedTutorials_Source_IntroTutorials_Private_EditorTutorialSettings_h_39_INCLASS \
private: \
	static void StaticRegisterNativesUEditorTutorialSettings(); \
	friend struct Z_Construct_UClass_UEditorTutorialSettings_Statics; \
public: \
	DECLARE_CLASS(UEditorTutorialSettings, UObject, COMPILED_IN_FLAGS(0 | CLASS_Config), CASTCLASS_None, TEXT("/Script/IntroTutorials"), NO_API) \
	DECLARE_SERIALIZER(UEditorTutorialSettings) \
	static const TCHAR* StaticConfigName() {return TEXT("GuidedTutorials");} \



#define FID_Mineprep_last_0_4_Plugins_GuidedTutorials_Source_IntroTutorials_Private_EditorTutorialSettings_h_39_STANDARD_CONSTRUCTORS \
	/** Standard constructor, called after all reflected properties have been initialized */ \
	NO_API UEditorTutorialSettings(const FObjectInitializer& ObjectInitializer = FObjectInitializer::Get()); \
	DEFINE_DEFAULT_OBJECT_INITIALIZER_CONSTRUCTOR_CALL(UEditorTutorialSettings) \
	DECLARE_VTABLE_PTR_HELPER_CTOR(NO_API, UEditorTutorialSettings); \
	DEFINE_VTABLE_PTR_HELPER_CTOR_CALLER(UEditorTutorialSettings); \
private: \
	/** Private move- and copy-constructors, should never be used */ \
	UEditorTutorialSettings(UEditorTutorialSettings&&); \
	UEditorTutorialSettings(const UEditorTutorialSettings&); \
public: \
	NO_API virtual ~UEditorTutorialSettings();


#define FID_Mineprep_last_0_4_Plugins_GuidedTutorials_Source_IntroTutorials_Private_EditorTutorialSettings_h_36_PROLOG
#define FID_Mineprep_last_0_4_Plugins_GuidedTutorials_Source_IntroTutorials_Private_EditorTutorialSettings_h_39_GENERATED_BODY_LEGACY \
PRAGMA_DISABLE_DEPRECATION_WARNINGS \
public: \
	FID_Mineprep_last_0_4_Plugins_GuidedTutorials_Source_IntroTutorials_Private_EditorTutorialSettings_h_39_INCLASS \
	FID_Mineprep_last_0_4_Plugins_GuidedTutorials_Source_IntroTutorials_Private_EditorTutorialSettings_h_39_STANDARD_CONSTRUCTORS \
public: \
PRAGMA_ENABLE_DEPRECATION_WARNINGS


template<> INTROTUTORIALS_API UClass* StaticClass<class UEditorTutorialSettings>();

#undef CURRENT_FILE_ID
#define CURRENT_FILE_ID FID_Mineprep_last_0_4_Plugins_GuidedTutorials_Source_IntroTutorials_Private_EditorTutorialSettings_h


PRAGMA_ENABLE_DEPRECATION_WARNINGS
