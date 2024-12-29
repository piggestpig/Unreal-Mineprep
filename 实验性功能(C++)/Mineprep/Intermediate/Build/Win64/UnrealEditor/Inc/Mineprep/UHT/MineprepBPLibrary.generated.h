// Copyright Epic Games, Inc. All Rights Reserved.
/*===========================================================================
	Generated code exported from UnrealHeaderTool.
	DO NOT modify this manually! Edit the corresponding .h files instead!
===========================================================================*/

// IWYU pragma: private, include "MineprepBPLibrary.h"
#include "UObject/ObjectMacros.h"
#include "UObject/ScriptMacros.h"

PRAGMA_DISABLE_DEPRECATION_WARNINGS
class UObject;
#ifdef MINEPREP_MineprepBPLibrary_generated_h
#error "MineprepBPLibrary.generated.h already included, missing '#pragma once' in MineprepBPLibrary.h"
#endif
#define MINEPREP_MineprepBPLibrary_generated_h

#define FID_Mineprep_last_0_4_Plugins_Mineprep_Source_Mineprep_Public_MineprepBPLibrary_h_17_RPC_WRAPPERS \
	DECLARE_FUNCTION(execSetTickRunOnAnyThread); \
	DECLARE_FUNCTION(execGetWidgetTextUnderMouse); \
	DECLARE_FUNCTION(execSetCameraPreviewSize); \
	DECLARE_FUNCTION(execSetPreviewSelectedCameras); \
	DECLARE_FUNCTION(execSetEditorUIScale);


#define FID_Mineprep_last_0_4_Plugins_Mineprep_Source_Mineprep_Public_MineprepBPLibrary_h_17_INCLASS \
private: \
	static void StaticRegisterNativesUmineprep(); \
	friend struct Z_Construct_UClass_Umineprep_Statics; \
public: \
	DECLARE_CLASS(Umineprep, UBlueprintFunctionLibrary, COMPILED_IN_FLAGS(0), CASTCLASS_None, TEXT("/Script/Mineprep"), NO_API) \
	DECLARE_SERIALIZER(Umineprep)


#define FID_Mineprep_last_0_4_Plugins_Mineprep_Source_Mineprep_Public_MineprepBPLibrary_h_17_STANDARD_CONSTRUCTORS \
	/** Standard constructor, called after all reflected properties have been initialized */ \
	NO_API Umineprep(const FObjectInitializer& ObjectInitializer = FObjectInitializer::Get()); \
	DEFINE_DEFAULT_OBJECT_INITIALIZER_CONSTRUCTOR_CALL(Umineprep) \
	DECLARE_VTABLE_PTR_HELPER_CTOR(NO_API, Umineprep); \
	DEFINE_VTABLE_PTR_HELPER_CTOR_CALLER(Umineprep); \
private: \
	/** Private move- and copy-constructors, should never be used */ \
	Umineprep(Umineprep&&); \
	Umineprep(const Umineprep&); \
public: \
	NO_API virtual ~Umineprep();


#define FID_Mineprep_last_0_4_Plugins_Mineprep_Source_Mineprep_Public_MineprepBPLibrary_h_14_PROLOG
#define FID_Mineprep_last_0_4_Plugins_Mineprep_Source_Mineprep_Public_MineprepBPLibrary_h_17_GENERATED_BODY_LEGACY \
PRAGMA_DISABLE_DEPRECATION_WARNINGS \
public: \
	FID_Mineprep_last_0_4_Plugins_Mineprep_Source_Mineprep_Public_MineprepBPLibrary_h_17_RPC_WRAPPERS \
	FID_Mineprep_last_0_4_Plugins_Mineprep_Source_Mineprep_Public_MineprepBPLibrary_h_17_INCLASS \
	FID_Mineprep_last_0_4_Plugins_Mineprep_Source_Mineprep_Public_MineprepBPLibrary_h_17_STANDARD_CONSTRUCTORS \
public: \
PRAGMA_ENABLE_DEPRECATION_WARNINGS


template<> MINEPREP_API UClass* StaticClass<class Umineprep>();

#undef CURRENT_FILE_ID
#define CURRENT_FILE_ID FID_Mineprep_last_0_4_Plugins_Mineprep_Source_Mineprep_Public_MineprepBPLibrary_h


PRAGMA_ENABLE_DEPRECATION_WARNINGS
