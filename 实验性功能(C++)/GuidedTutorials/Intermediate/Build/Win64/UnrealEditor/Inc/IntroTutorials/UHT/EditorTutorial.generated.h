// Copyright Epic Games, Inc. All Rights Reserved.
/*===========================================================================
	Generated code exported from UnrealHeaderTool.
	DO NOT modify this manually! Edit the corresponding .h files instead!
===========================================================================*/

// IWYU pragma: private, include "EditorTutorial.h"
#include "UObject/ObjectMacros.h"
#include "UObject/ScriptMacros.h"

PRAGMA_DISABLE_DEPRECATION_WARNINGS
class AActor;
class UEditorTutorial;
class UObject;
#ifdef INTROTUTORIALS_EditorTutorial_generated_h
#error "EditorTutorial.generated.h already included, missing '#pragma once' in EditorTutorial.h"
#endif
#define INTROTUTORIALS_EditorTutorial_generated_h

#define FID_Mineprep_last_0_4_Plugins_GuidedTutorials_Source_IntroTutorials_Public_EditorTutorial_h_57_GENERATED_BODY \
	friend struct Z_Construct_UScriptStruct_FTutorialCategory_Statics; \
	static class UScriptStruct* StaticStruct();


template<> INTROTUTORIALS_API UScriptStruct* StaticStruct<struct FTutorialCategory>();

#define FID_Mineprep_last_0_4_Plugins_GuidedTutorials_Source_IntroTutorials_Public_EditorTutorial_h_88_GENERATED_BODY \
	friend struct Z_Construct_UScriptStruct_FTutorialContent_Statics; \
	static class UScriptStruct* StaticStruct();


template<> INTROTUTORIALS_API UScriptStruct* StaticStruct<struct FTutorialContent>();

#define FID_Mineprep_last_0_4_Plugins_GuidedTutorials_Source_IntroTutorials_Public_EditorTutorial_h_116_GENERATED_BODY \
	friend struct Z_Construct_UScriptStruct_FTutorialContentAnchor_Statics; \
	static class UScriptStruct* StaticStruct();


template<> INTROTUTORIALS_API UScriptStruct* StaticStruct<struct FTutorialContentAnchor>();

#define FID_Mineprep_last_0_4_Plugins_GuidedTutorials_Source_IntroTutorials_Public_EditorTutorial_h_161_GENERATED_BODY \
	friend struct Z_Construct_UScriptStruct_FTutorialWidgetContent_Statics; \
	static class UScriptStruct* StaticStruct();


template<> INTROTUTORIALS_API UScriptStruct* StaticStruct<struct FTutorialWidgetContent>();

#define FID_Mineprep_last_0_4_Plugins_GuidedTutorials_Source_IntroTutorials_Public_EditorTutorial_h_203_GENERATED_BODY \
	friend struct Z_Construct_UScriptStruct_FTutorialStage_Statics; \
	static class UScriptStruct* StaticStruct();


template<> INTROTUTORIALS_API UScriptStruct* StaticStruct<struct FTutorialStage>();

#define FID_Mineprep_last_0_4_Plugins_GuidedTutorials_Source_IntroTutorials_Public_EditorTutorial_h_238_RPC_WRAPPERS \
	DECLARE_FUNCTION(execGetEngineFolderVisibilty); \
	DECLARE_FUNCTION(execSetEngineFolderVisibilty); \
	DECLARE_FUNCTION(execOpenAsset); \
	DECLARE_FUNCTION(execBeginTutorial); \
	DECLARE_FUNCTION(execGoToPreviousTutorialStage); \
	DECLARE_FUNCTION(execGoToNextTutorialStage); \
	DECLARE_FUNCTION(execGetActorReference);


#define FID_Mineprep_last_0_4_Plugins_GuidedTutorials_Source_IntroTutorials_Public_EditorTutorial_h_238_CALLBACK_WRAPPERS
#define FID_Mineprep_last_0_4_Plugins_GuidedTutorials_Source_IntroTutorials_Public_EditorTutorial_h_238_INCLASS \
private: \
	static void StaticRegisterNativesUEditorTutorial(); \
	friend struct Z_Construct_UClass_UEditorTutorial_Statics; \
public: \
	DECLARE_CLASS(UEditorTutorial, UObject, COMPILED_IN_FLAGS(0), CASTCLASS_None, TEXT("/Script/IntroTutorials"), NO_API) \
	DECLARE_SERIALIZER(UEditorTutorial)


#define FID_Mineprep_last_0_4_Plugins_GuidedTutorials_Source_IntroTutorials_Public_EditorTutorial_h_238_STANDARD_CONSTRUCTORS \
	/** Standard constructor, called after all reflected properties have been initialized */ \
	NO_API UEditorTutorial(const FObjectInitializer& ObjectInitializer = FObjectInitializer::Get()); \
	DEFINE_DEFAULT_OBJECT_INITIALIZER_CONSTRUCTOR_CALL(UEditorTutorial) \
	DECLARE_VTABLE_PTR_HELPER_CTOR(NO_API, UEditorTutorial); \
	DEFINE_VTABLE_PTR_HELPER_CTOR_CALLER(UEditorTutorial); \
private: \
	/** Private move- and copy-constructors, should never be used */ \
	UEditorTutorial(UEditorTutorial&&); \
	UEditorTutorial(const UEditorTutorial&); \
public: \
	NO_API virtual ~UEditorTutorial();


#define FID_Mineprep_last_0_4_Plugins_GuidedTutorials_Source_IntroTutorials_Public_EditorTutorial_h_235_PROLOG
#define FID_Mineprep_last_0_4_Plugins_GuidedTutorials_Source_IntroTutorials_Public_EditorTutorial_h_238_GENERATED_BODY_LEGACY \
PRAGMA_DISABLE_DEPRECATION_WARNINGS \
public: \
	FID_Mineprep_last_0_4_Plugins_GuidedTutorials_Source_IntroTutorials_Public_EditorTutorial_h_238_RPC_WRAPPERS \
	FID_Mineprep_last_0_4_Plugins_GuidedTutorials_Source_IntroTutorials_Public_EditorTutorial_h_238_CALLBACK_WRAPPERS \
	FID_Mineprep_last_0_4_Plugins_GuidedTutorials_Source_IntroTutorials_Public_EditorTutorial_h_238_INCLASS \
	FID_Mineprep_last_0_4_Plugins_GuidedTutorials_Source_IntroTutorials_Public_EditorTutorial_h_238_STANDARD_CONSTRUCTORS \
public: \
PRAGMA_ENABLE_DEPRECATION_WARNINGS


template<> INTROTUTORIALS_API UClass* StaticClass<class UEditorTutorial>();

#undef CURRENT_FILE_ID
#define CURRENT_FILE_ID FID_Mineprep_last_0_4_Plugins_GuidedTutorials_Source_IntroTutorials_Public_EditorTutorial_h


#define FOREACH_ENUM_ETUTORIALCONTENT(op) \
	op(ETutorialContent::None) \
	op(ETutorialContent::Text) \
	op(ETutorialContent::UDNExcerpt) \
	op(ETutorialContent::RichText) 

namespace ETutorialContent { enum Type : int; }
template<> INTROTUTORIALS_API UEnum* StaticEnum<ETutorialContent::Type>();

#define FOREACH_ENUM_ETUTORIALANCHORIDENTIFIER(op) \
	op(ETutorialAnchorIdentifier::None) \
	op(ETutorialAnchorIdentifier::NamedWidget) \
	op(ETutorialAnchorIdentifier::Asset) 

namespace ETutorialAnchorIdentifier { enum Type : int; }
template<> INTROTUTORIALS_API UEnum* StaticEnum<ETutorialAnchorIdentifier::Type>();

PRAGMA_ENABLE_DEPRECATION_WARNINGS
