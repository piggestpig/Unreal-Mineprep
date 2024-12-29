// Copyright Epic Games, Inc. All Rights Reserved.
/*===========================================================================
	Generated code exported from UnrealHeaderTool.
	DO NOT modify this manually! Edit the corresponding .h files instead!
===========================================================================*/

// IWYU pragma: private, include "TutorialSettings.h"
#include "UObject/ObjectMacros.h"
#include "UObject/ScriptMacros.h"

PRAGMA_DISABLE_DEPRECATION_WARNINGS
#ifdef INTROTUTORIALS_TutorialSettings_generated_h
#error "TutorialSettings.generated.h already included, missing '#pragma once' in TutorialSettings.h"
#endif
#define INTROTUTORIALS_TutorialSettings_generated_h

#define FID_Mineprep_last_0_4_Plugins_GuidedTutorials_Source_IntroTutorials_Private_TutorialSettings_h_16_INCLASS \
private: \
	static void StaticRegisterNativesUTutorialSettings(); \
	friend struct Z_Construct_UClass_UTutorialSettings_Statics; \
public: \
	DECLARE_CLASS(UTutorialSettings, UObject, COMPILED_IN_FLAGS(0 | CLASS_Config), CASTCLASS_None, TEXT("/Script/IntroTutorials"), NO_API) \
	DECLARE_SERIALIZER(UTutorialSettings) \
	static const TCHAR* StaticConfigName() {return TEXT("Editor");} \



#define FID_Mineprep_last_0_4_Plugins_GuidedTutorials_Source_IntroTutorials_Private_TutorialSettings_h_16_STANDARD_CONSTRUCTORS \
	/** Standard constructor, called after all reflected properties have been initialized */ \
	NO_API UTutorialSettings(const FObjectInitializer& ObjectInitializer = FObjectInitializer::Get()); \
	DEFINE_DEFAULT_OBJECT_INITIALIZER_CONSTRUCTOR_CALL(UTutorialSettings) \
	DECLARE_VTABLE_PTR_HELPER_CTOR(NO_API, UTutorialSettings); \
	DEFINE_VTABLE_PTR_HELPER_CTOR_CALLER(UTutorialSettings); \
private: \
	/** Private move- and copy-constructors, should never be used */ \
	UTutorialSettings(UTutorialSettings&&); \
	UTutorialSettings(const UTutorialSettings&); \
public: \
	NO_API virtual ~UTutorialSettings();


#define FID_Mineprep_last_0_4_Plugins_GuidedTutorials_Source_IntroTutorials_Private_TutorialSettings_h_13_PROLOG
#define FID_Mineprep_last_0_4_Plugins_GuidedTutorials_Source_IntroTutorials_Private_TutorialSettings_h_16_GENERATED_BODY_LEGACY \
PRAGMA_DISABLE_DEPRECATION_WARNINGS \
public: \
	FID_Mineprep_last_0_4_Plugins_GuidedTutorials_Source_IntroTutorials_Private_TutorialSettings_h_16_INCLASS \
	FID_Mineprep_last_0_4_Plugins_GuidedTutorials_Source_IntroTutorials_Private_TutorialSettings_h_16_STANDARD_CONSTRUCTORS \
public: \
PRAGMA_ENABLE_DEPRECATION_WARNINGS


template<> INTROTUTORIALS_API UClass* StaticClass<class UTutorialSettings>();

#undef CURRENT_FILE_ID
#define CURRENT_FILE_ID FID_Mineprep_last_0_4_Plugins_GuidedTutorials_Source_IntroTutorials_Private_TutorialSettings_h


PRAGMA_ENABLE_DEPRECATION_WARNINGS
