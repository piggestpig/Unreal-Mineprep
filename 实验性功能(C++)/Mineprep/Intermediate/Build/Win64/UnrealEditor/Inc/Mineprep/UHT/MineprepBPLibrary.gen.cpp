// Copyright Epic Games, Inc. All Rights Reserved.
/*===========================================================================
	Generated code exported from UnrealHeaderTool.
	DO NOT modify this manually! Edit the corresponding .h files instead!
===========================================================================*/

#include "UObject/GeneratedCppIncludes.h"
#include "Mineprep/Public/MineprepBPLibrary.h"
#include "Runtime/MovieSceneTracks/Public/Tracks/MovieSceneMaterialTrack.h"
PRAGMA_DISABLE_DEPRECATION_WARNINGS
void EmptyLinkFunctionForGeneratedCodeMineprepBPLibrary() {}

// Begin Cross Module References
COREUOBJECT_API UClass* Z_Construct_UClass_UObject_NoRegister();
ENGINE_API UClass* Z_Construct_UClass_UBlueprintFunctionLibrary();
MINEPREP_API UClass* Z_Construct_UClass_Umineprep();
MINEPREP_API UClass* Z_Construct_UClass_Umineprep_NoRegister();
MOVIESCENETRACKS_API UClass* Z_Construct_UClass_UMovieSceneComponentMaterialTrack_NoRegister();
MOVIESCENETRACKS_API UScriptStruct* Z_Construct_UScriptStruct_FComponentMaterialInfo();
UPackage* Z_Construct_UPackage__Script_Mineprep();
// End Cross Module References

// Begin Class Umineprep Function GetMaterialInfo
struct Z_Construct_UFunction_Umineprep_GetMaterialInfo_Statics
{
	struct mineprep_eventGetMaterialInfo_Parms
	{
		UMovieSceneComponentMaterialTrack* Track;
		FComponentMaterialInfo ReturnValue;
	};
#if WITH_METADATA
	static constexpr UECodeGen_Private::FMetaDataPairParam Function_MetaDataParams[] = {
		{ "Category", "Mineprep|\xe5\xae\x9e\xe9\xaa\x8c\xe6\x80\xa7\xe5\x8a\x9f\xe8\x83\xbd(C++)" },
		{ "DisplayName", "Get Material Info" },
		{ "Keywords", "Mineprep Material Info" },
		{ "ModuleRelativePath", "Public/MineprepBPLibrary.h" },
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_Track_MetaData[] = {
		{ "EditInline", "true" },
	};
#endif // WITH_METADATA
	static const UECodeGen_Private::FObjectPropertyParams NewProp_Track;
	static const UECodeGen_Private::FStructPropertyParams NewProp_ReturnValue;
	static const UECodeGen_Private::FPropertyParamsBase* const PropPointers[];
	static const UECodeGen_Private::FFunctionParams FuncParams;
};
const UECodeGen_Private::FObjectPropertyParams Z_Construct_UFunction_Umineprep_GetMaterialInfo_Statics::NewProp_Track = { "Track", nullptr, (EPropertyFlags)0x0010000000080080, UECodeGen_Private::EPropertyGenFlags::Object, RF_Public|RF_Transient|RF_MarkAsNative, nullptr, nullptr, 1, STRUCT_OFFSET(mineprep_eventGetMaterialInfo_Parms, Track), Z_Construct_UClass_UMovieSceneComponentMaterialTrack_NoRegister, METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_Track_MetaData), NewProp_Track_MetaData) };
const UECodeGen_Private::FStructPropertyParams Z_Construct_UFunction_Umineprep_GetMaterialInfo_Statics::NewProp_ReturnValue = { "ReturnValue", nullptr, (EPropertyFlags)0x0010000000000580, UECodeGen_Private::EPropertyGenFlags::Struct, RF_Public|RF_Transient|RF_MarkAsNative, nullptr, nullptr, 1, STRUCT_OFFSET(mineprep_eventGetMaterialInfo_Parms, ReturnValue), Z_Construct_UScriptStruct_FComponentMaterialInfo, METADATA_PARAMS(0, nullptr) }; // 3517514751
const UECodeGen_Private::FPropertyParamsBase* const Z_Construct_UFunction_Umineprep_GetMaterialInfo_Statics::PropPointers[] = {
	(const UECodeGen_Private::FPropertyParamsBase*)&Z_Construct_UFunction_Umineprep_GetMaterialInfo_Statics::NewProp_Track,
	(const UECodeGen_Private::FPropertyParamsBase*)&Z_Construct_UFunction_Umineprep_GetMaterialInfo_Statics::NewProp_ReturnValue,
};
static_assert(UE_ARRAY_COUNT(Z_Construct_UFunction_Umineprep_GetMaterialInfo_Statics::PropPointers) < 2048);
const UECodeGen_Private::FFunctionParams Z_Construct_UFunction_Umineprep_GetMaterialInfo_Statics::FuncParams = { (UObject*(*)())Z_Construct_UClass_Umineprep, nullptr, "GetMaterialInfo", nullptr, nullptr, Z_Construct_UFunction_Umineprep_GetMaterialInfo_Statics::PropPointers, UE_ARRAY_COUNT(Z_Construct_UFunction_Umineprep_GetMaterialInfo_Statics::PropPointers), sizeof(Z_Construct_UFunction_Umineprep_GetMaterialInfo_Statics::mineprep_eventGetMaterialInfo_Parms), RF_Public|RF_Transient|RF_MarkAsNative, (EFunctionFlags)0x04022401, 0, 0, METADATA_PARAMS(UE_ARRAY_COUNT(Z_Construct_UFunction_Umineprep_GetMaterialInfo_Statics::Function_MetaDataParams), Z_Construct_UFunction_Umineprep_GetMaterialInfo_Statics::Function_MetaDataParams) };
static_assert(sizeof(Z_Construct_UFunction_Umineprep_GetMaterialInfo_Statics::mineprep_eventGetMaterialInfo_Parms) < MAX_uint16);
UFunction* Z_Construct_UFunction_Umineprep_GetMaterialInfo()
{
	static UFunction* ReturnFunction = nullptr;
	if (!ReturnFunction)
	{
		UECodeGen_Private::ConstructUFunction(&ReturnFunction, Z_Construct_UFunction_Umineprep_GetMaterialInfo_Statics::FuncParams);
	}
	return ReturnFunction;
}
DEFINE_FUNCTION(Umineprep::execGetMaterialInfo)
{
	P_GET_OBJECT(UMovieSceneComponentMaterialTrack,Z_Param_Track);
	P_FINISH;
	P_NATIVE_BEGIN;
	*(FComponentMaterialInfo*)Z_Param__Result=Umineprep::GetMaterialInfo(Z_Param_Track);
	P_NATIVE_END;
}
// End Class Umineprep Function GetMaterialInfo

// Begin Class Umineprep Function GetWidgetTextUnderMouse
struct Z_Construct_UFunction_Umineprep_GetWidgetTextUnderMouse_Statics
{
	struct mineprep_eventGetWidgetTextUnderMouse_Parms
	{
		FString ReturnValue;
	};
#if WITH_METADATA
	static constexpr UECodeGen_Private::FMetaDataPairParam Function_MetaDataParams[] = {
		{ "Category", "Mineprep|\xe5\xae\x9e\xe9\xaa\x8c\xe6\x80\xa7\xe5\x8a\x9f\xe8\x83\xbd(C++)" },
		{ "DisplayName", "Get Widget Text Under Mouse" },
		{ "Keywords", "Mineprep UI Widget Text" },
		{ "ModuleRelativePath", "Public/MineprepBPLibrary.h" },
	};
#endif // WITH_METADATA
	static const UECodeGen_Private::FStrPropertyParams NewProp_ReturnValue;
	static const UECodeGen_Private::FPropertyParamsBase* const PropPointers[];
	static const UECodeGen_Private::FFunctionParams FuncParams;
};
const UECodeGen_Private::FStrPropertyParams Z_Construct_UFunction_Umineprep_GetWidgetTextUnderMouse_Statics::NewProp_ReturnValue = { "ReturnValue", nullptr, (EPropertyFlags)0x0010000000000580, UECodeGen_Private::EPropertyGenFlags::Str, RF_Public|RF_Transient|RF_MarkAsNative, nullptr, nullptr, 1, STRUCT_OFFSET(mineprep_eventGetWidgetTextUnderMouse_Parms, ReturnValue), METADATA_PARAMS(0, nullptr) };
const UECodeGen_Private::FPropertyParamsBase* const Z_Construct_UFunction_Umineprep_GetWidgetTextUnderMouse_Statics::PropPointers[] = {
	(const UECodeGen_Private::FPropertyParamsBase*)&Z_Construct_UFunction_Umineprep_GetWidgetTextUnderMouse_Statics::NewProp_ReturnValue,
};
static_assert(UE_ARRAY_COUNT(Z_Construct_UFunction_Umineprep_GetWidgetTextUnderMouse_Statics::PropPointers) < 2048);
const UECodeGen_Private::FFunctionParams Z_Construct_UFunction_Umineprep_GetWidgetTextUnderMouse_Statics::FuncParams = { (UObject*(*)())Z_Construct_UClass_Umineprep, nullptr, "GetWidgetTextUnderMouse", nullptr, nullptr, Z_Construct_UFunction_Umineprep_GetWidgetTextUnderMouse_Statics::PropPointers, UE_ARRAY_COUNT(Z_Construct_UFunction_Umineprep_GetWidgetTextUnderMouse_Statics::PropPointers), sizeof(Z_Construct_UFunction_Umineprep_GetWidgetTextUnderMouse_Statics::mineprep_eventGetWidgetTextUnderMouse_Parms), RF_Public|RF_Transient|RF_MarkAsNative, (EFunctionFlags)0x04022401, 0, 0, METADATA_PARAMS(UE_ARRAY_COUNT(Z_Construct_UFunction_Umineprep_GetWidgetTextUnderMouse_Statics::Function_MetaDataParams), Z_Construct_UFunction_Umineprep_GetWidgetTextUnderMouse_Statics::Function_MetaDataParams) };
static_assert(sizeof(Z_Construct_UFunction_Umineprep_GetWidgetTextUnderMouse_Statics::mineprep_eventGetWidgetTextUnderMouse_Parms) < MAX_uint16);
UFunction* Z_Construct_UFunction_Umineprep_GetWidgetTextUnderMouse()
{
	static UFunction* ReturnFunction = nullptr;
	if (!ReturnFunction)
	{
		UECodeGen_Private::ConstructUFunction(&ReturnFunction, Z_Construct_UFunction_Umineprep_GetWidgetTextUnderMouse_Statics::FuncParams);
	}
	return ReturnFunction;
}
DEFINE_FUNCTION(Umineprep::execGetWidgetTextUnderMouse)
{
	P_FINISH;
	P_NATIVE_BEGIN;
	*(FString*)Z_Param__Result=Umineprep::GetWidgetTextUnderMouse();
	P_NATIVE_END;
}
// End Class Umineprep Function GetWidgetTextUnderMouse

// Begin Class Umineprep Function SetCameraPreviewSize
struct Z_Construct_UFunction_Umineprep_SetCameraPreviewSize_Statics
{
	struct mineprep_eventSetCameraPreviewSize_Parms
	{
		float PreviewSize;
	};
#if WITH_METADATA
	static constexpr UECodeGen_Private::FMetaDataPairParam Function_MetaDataParams[] = {
		{ "Category", "Mineprep|\xe5\xae\x9e\xe9\xaa\x8c\xe6\x80\xa7\xe5\x8a\x9f\xe8\x83\xbd(C++)" },
		{ "DisplayName", "Set Camera Preview Size" },
		{ "Keywords", "Mineprep Camera Preview" },
		{ "ModuleRelativePath", "Public/MineprepBPLibrary.h" },
	};
#endif // WITH_METADATA
	static const UECodeGen_Private::FFloatPropertyParams NewProp_PreviewSize;
	static const UECodeGen_Private::FPropertyParamsBase* const PropPointers[];
	static const UECodeGen_Private::FFunctionParams FuncParams;
};
const UECodeGen_Private::FFloatPropertyParams Z_Construct_UFunction_Umineprep_SetCameraPreviewSize_Statics::NewProp_PreviewSize = { "PreviewSize", nullptr, (EPropertyFlags)0x0010000000000080, UECodeGen_Private::EPropertyGenFlags::Float, RF_Public|RF_Transient|RF_MarkAsNative, nullptr, nullptr, 1, STRUCT_OFFSET(mineprep_eventSetCameraPreviewSize_Parms, PreviewSize), METADATA_PARAMS(0, nullptr) };
const UECodeGen_Private::FPropertyParamsBase* const Z_Construct_UFunction_Umineprep_SetCameraPreviewSize_Statics::PropPointers[] = {
	(const UECodeGen_Private::FPropertyParamsBase*)&Z_Construct_UFunction_Umineprep_SetCameraPreviewSize_Statics::NewProp_PreviewSize,
};
static_assert(UE_ARRAY_COUNT(Z_Construct_UFunction_Umineprep_SetCameraPreviewSize_Statics::PropPointers) < 2048);
const UECodeGen_Private::FFunctionParams Z_Construct_UFunction_Umineprep_SetCameraPreviewSize_Statics::FuncParams = { (UObject*(*)())Z_Construct_UClass_Umineprep, nullptr, "SetCameraPreviewSize", nullptr, nullptr, Z_Construct_UFunction_Umineprep_SetCameraPreviewSize_Statics::PropPointers, UE_ARRAY_COUNT(Z_Construct_UFunction_Umineprep_SetCameraPreviewSize_Statics::PropPointers), sizeof(Z_Construct_UFunction_Umineprep_SetCameraPreviewSize_Statics::mineprep_eventSetCameraPreviewSize_Parms), RF_Public|RF_Transient|RF_MarkAsNative, (EFunctionFlags)0x04022401, 0, 0, METADATA_PARAMS(UE_ARRAY_COUNT(Z_Construct_UFunction_Umineprep_SetCameraPreviewSize_Statics::Function_MetaDataParams), Z_Construct_UFunction_Umineprep_SetCameraPreviewSize_Statics::Function_MetaDataParams) };
static_assert(sizeof(Z_Construct_UFunction_Umineprep_SetCameraPreviewSize_Statics::mineprep_eventSetCameraPreviewSize_Parms) < MAX_uint16);
UFunction* Z_Construct_UFunction_Umineprep_SetCameraPreviewSize()
{
	static UFunction* ReturnFunction = nullptr;
	if (!ReturnFunction)
	{
		UECodeGen_Private::ConstructUFunction(&ReturnFunction, Z_Construct_UFunction_Umineprep_SetCameraPreviewSize_Statics::FuncParams);
	}
	return ReturnFunction;
}
DEFINE_FUNCTION(Umineprep::execSetCameraPreviewSize)
{
	P_GET_PROPERTY(FFloatProperty,Z_Param_PreviewSize);
	P_FINISH;
	P_NATIVE_BEGIN;
	Umineprep::SetCameraPreviewSize(Z_Param_PreviewSize);
	P_NATIVE_END;
}
// End Class Umineprep Function SetCameraPreviewSize

// Begin Class Umineprep Function SetEditorUIScale
struct Z_Construct_UFunction_Umineprep_SetEditorUIScale_Statics
{
	struct mineprep_eventSetEditorUIScale_Parms
	{
		float Scale;
		float ReturnValue;
	};
#if WITH_METADATA
	static constexpr UECodeGen_Private::FMetaDataPairParam Function_MetaDataParams[] = {
		{ "Category", "Mineprep|\xe5\xae\x9e\xe9\xaa\x8c\xe6\x80\xa7\xe5\x8a\x9f\xe8\x83\xbd(C++)" },
		{ "DisplayName", "Set Editor UI Scale" },
		{ "Keywords", "Mineprep UI Scale Editor" },
		{ "ModuleRelativePath", "Public/MineprepBPLibrary.h" },
	};
#endif // WITH_METADATA
	static const UECodeGen_Private::FFloatPropertyParams NewProp_Scale;
	static const UECodeGen_Private::FFloatPropertyParams NewProp_ReturnValue;
	static const UECodeGen_Private::FPropertyParamsBase* const PropPointers[];
	static const UECodeGen_Private::FFunctionParams FuncParams;
};
const UECodeGen_Private::FFloatPropertyParams Z_Construct_UFunction_Umineprep_SetEditorUIScale_Statics::NewProp_Scale = { "Scale", nullptr, (EPropertyFlags)0x0010000000000080, UECodeGen_Private::EPropertyGenFlags::Float, RF_Public|RF_Transient|RF_MarkAsNative, nullptr, nullptr, 1, STRUCT_OFFSET(mineprep_eventSetEditorUIScale_Parms, Scale), METADATA_PARAMS(0, nullptr) };
const UECodeGen_Private::FFloatPropertyParams Z_Construct_UFunction_Umineprep_SetEditorUIScale_Statics::NewProp_ReturnValue = { "ReturnValue", nullptr, (EPropertyFlags)0x0010000000000580, UECodeGen_Private::EPropertyGenFlags::Float, RF_Public|RF_Transient|RF_MarkAsNative, nullptr, nullptr, 1, STRUCT_OFFSET(mineprep_eventSetEditorUIScale_Parms, ReturnValue), METADATA_PARAMS(0, nullptr) };
const UECodeGen_Private::FPropertyParamsBase* const Z_Construct_UFunction_Umineprep_SetEditorUIScale_Statics::PropPointers[] = {
	(const UECodeGen_Private::FPropertyParamsBase*)&Z_Construct_UFunction_Umineprep_SetEditorUIScale_Statics::NewProp_Scale,
	(const UECodeGen_Private::FPropertyParamsBase*)&Z_Construct_UFunction_Umineprep_SetEditorUIScale_Statics::NewProp_ReturnValue,
};
static_assert(UE_ARRAY_COUNT(Z_Construct_UFunction_Umineprep_SetEditorUIScale_Statics::PropPointers) < 2048);
const UECodeGen_Private::FFunctionParams Z_Construct_UFunction_Umineprep_SetEditorUIScale_Statics::FuncParams = { (UObject*(*)())Z_Construct_UClass_Umineprep, nullptr, "SetEditorUIScale", nullptr, nullptr, Z_Construct_UFunction_Umineprep_SetEditorUIScale_Statics::PropPointers, UE_ARRAY_COUNT(Z_Construct_UFunction_Umineprep_SetEditorUIScale_Statics::PropPointers), sizeof(Z_Construct_UFunction_Umineprep_SetEditorUIScale_Statics::mineprep_eventSetEditorUIScale_Parms), RF_Public|RF_Transient|RF_MarkAsNative, (EFunctionFlags)0x04022401, 0, 0, METADATA_PARAMS(UE_ARRAY_COUNT(Z_Construct_UFunction_Umineprep_SetEditorUIScale_Statics::Function_MetaDataParams), Z_Construct_UFunction_Umineprep_SetEditorUIScale_Statics::Function_MetaDataParams) };
static_assert(sizeof(Z_Construct_UFunction_Umineprep_SetEditorUIScale_Statics::mineprep_eventSetEditorUIScale_Parms) < MAX_uint16);
UFunction* Z_Construct_UFunction_Umineprep_SetEditorUIScale()
{
	static UFunction* ReturnFunction = nullptr;
	if (!ReturnFunction)
	{
		UECodeGen_Private::ConstructUFunction(&ReturnFunction, Z_Construct_UFunction_Umineprep_SetEditorUIScale_Statics::FuncParams);
	}
	return ReturnFunction;
}
DEFINE_FUNCTION(Umineprep::execSetEditorUIScale)
{
	P_GET_PROPERTY(FFloatProperty,Z_Param_Scale);
	P_FINISH;
	P_NATIVE_BEGIN;
	*(float*)Z_Param__Result=Umineprep::SetEditorUIScale(Z_Param_Scale);
	P_NATIVE_END;
}
// End Class Umineprep Function SetEditorUIScale

// Begin Class Umineprep Function SetPreviewSelectedCameras
struct Z_Construct_UFunction_Umineprep_SetPreviewSelectedCameras_Statics
{
	struct mineprep_eventSetPreviewSelectedCameras_Parms
	{
		bool bPreview;
	};
#if WITH_METADATA
	static constexpr UECodeGen_Private::FMetaDataPairParam Function_MetaDataParams[] = {
		{ "Category", "Mineprep|\xe5\xae\x9e\xe9\xaa\x8c\xe6\x80\xa7\xe5\x8a\x9f\xe8\x83\xbd(C++)" },
		{ "DisplayName", "Set Preview Selected Cameras" },
		{ "Keywords", "Mineprep Camera Preview" },
		{ "ModuleRelativePath", "Public/MineprepBPLibrary.h" },
	};
#endif // WITH_METADATA
	static void NewProp_bPreview_SetBit(void* Obj);
	static const UECodeGen_Private::FBoolPropertyParams NewProp_bPreview;
	static const UECodeGen_Private::FPropertyParamsBase* const PropPointers[];
	static const UECodeGen_Private::FFunctionParams FuncParams;
};
void Z_Construct_UFunction_Umineprep_SetPreviewSelectedCameras_Statics::NewProp_bPreview_SetBit(void* Obj)
{
	((mineprep_eventSetPreviewSelectedCameras_Parms*)Obj)->bPreview = 1;
}
const UECodeGen_Private::FBoolPropertyParams Z_Construct_UFunction_Umineprep_SetPreviewSelectedCameras_Statics::NewProp_bPreview = { "bPreview", nullptr, (EPropertyFlags)0x0010000000000080, UECodeGen_Private::EPropertyGenFlags::Bool | UECodeGen_Private::EPropertyGenFlags::NativeBool, RF_Public|RF_Transient|RF_MarkAsNative, nullptr, nullptr, 1, sizeof(bool), sizeof(mineprep_eventSetPreviewSelectedCameras_Parms), &Z_Construct_UFunction_Umineprep_SetPreviewSelectedCameras_Statics::NewProp_bPreview_SetBit, METADATA_PARAMS(0, nullptr) };
const UECodeGen_Private::FPropertyParamsBase* const Z_Construct_UFunction_Umineprep_SetPreviewSelectedCameras_Statics::PropPointers[] = {
	(const UECodeGen_Private::FPropertyParamsBase*)&Z_Construct_UFunction_Umineprep_SetPreviewSelectedCameras_Statics::NewProp_bPreview,
};
static_assert(UE_ARRAY_COUNT(Z_Construct_UFunction_Umineprep_SetPreviewSelectedCameras_Statics::PropPointers) < 2048);
const UECodeGen_Private::FFunctionParams Z_Construct_UFunction_Umineprep_SetPreviewSelectedCameras_Statics::FuncParams = { (UObject*(*)())Z_Construct_UClass_Umineprep, nullptr, "SetPreviewSelectedCameras", nullptr, nullptr, Z_Construct_UFunction_Umineprep_SetPreviewSelectedCameras_Statics::PropPointers, UE_ARRAY_COUNT(Z_Construct_UFunction_Umineprep_SetPreviewSelectedCameras_Statics::PropPointers), sizeof(Z_Construct_UFunction_Umineprep_SetPreviewSelectedCameras_Statics::mineprep_eventSetPreviewSelectedCameras_Parms), RF_Public|RF_Transient|RF_MarkAsNative, (EFunctionFlags)0x04022401, 0, 0, METADATA_PARAMS(UE_ARRAY_COUNT(Z_Construct_UFunction_Umineprep_SetPreviewSelectedCameras_Statics::Function_MetaDataParams), Z_Construct_UFunction_Umineprep_SetPreviewSelectedCameras_Statics::Function_MetaDataParams) };
static_assert(sizeof(Z_Construct_UFunction_Umineprep_SetPreviewSelectedCameras_Statics::mineprep_eventSetPreviewSelectedCameras_Parms) < MAX_uint16);
UFunction* Z_Construct_UFunction_Umineprep_SetPreviewSelectedCameras()
{
	static UFunction* ReturnFunction = nullptr;
	if (!ReturnFunction)
	{
		UECodeGen_Private::ConstructUFunction(&ReturnFunction, Z_Construct_UFunction_Umineprep_SetPreviewSelectedCameras_Statics::FuncParams);
	}
	return ReturnFunction;
}
DEFINE_FUNCTION(Umineprep::execSetPreviewSelectedCameras)
{
	P_GET_UBOOL(Z_Param_bPreview);
	P_FINISH;
	P_NATIVE_BEGIN;
	Umineprep::SetPreviewSelectedCameras(Z_Param_bPreview);
	P_NATIVE_END;
}
// End Class Umineprep Function SetPreviewSelectedCameras

// Begin Class Umineprep Function SetTickRunOnAnyThread
struct Z_Construct_UFunction_Umineprep_SetTickRunOnAnyThread_Statics
{
	struct mineprep_eventSetTickRunOnAnyThread_Parms
	{
		UObject* Object;
		bool bRunOnAnyThread;
	};
#if WITH_METADATA
	static constexpr UECodeGen_Private::FMetaDataPairParam Function_MetaDataParams[] = {
		{ "Category", "Mineprep|\xe5\xae\x9e\xe9\xaa\x8c\xe6\x80\xa7\xe5\x8a\x9f\xe8\x83\xbd(C++)" },
		{ "DisplayName", "Set Tick Run On Any Thread" },
		{ "Keywords", "Mineprep Tick Thread" },
		{ "ModuleRelativePath", "Public/MineprepBPLibrary.h" },
	};
#endif // WITH_METADATA
	static const UECodeGen_Private::FObjectPropertyParams NewProp_Object;
	static void NewProp_bRunOnAnyThread_SetBit(void* Obj);
	static const UECodeGen_Private::FBoolPropertyParams NewProp_bRunOnAnyThread;
	static const UECodeGen_Private::FPropertyParamsBase* const PropPointers[];
	static const UECodeGen_Private::FFunctionParams FuncParams;
};
const UECodeGen_Private::FObjectPropertyParams Z_Construct_UFunction_Umineprep_SetTickRunOnAnyThread_Statics::NewProp_Object = { "Object", nullptr, (EPropertyFlags)0x0010000000000080, UECodeGen_Private::EPropertyGenFlags::Object, RF_Public|RF_Transient|RF_MarkAsNative, nullptr, nullptr, 1, STRUCT_OFFSET(mineprep_eventSetTickRunOnAnyThread_Parms, Object), Z_Construct_UClass_UObject_NoRegister, METADATA_PARAMS(0, nullptr) };
void Z_Construct_UFunction_Umineprep_SetTickRunOnAnyThread_Statics::NewProp_bRunOnAnyThread_SetBit(void* Obj)
{
	((mineprep_eventSetTickRunOnAnyThread_Parms*)Obj)->bRunOnAnyThread = 1;
}
const UECodeGen_Private::FBoolPropertyParams Z_Construct_UFunction_Umineprep_SetTickRunOnAnyThread_Statics::NewProp_bRunOnAnyThread = { "bRunOnAnyThread", nullptr, (EPropertyFlags)0x0010000000000080, UECodeGen_Private::EPropertyGenFlags::Bool | UECodeGen_Private::EPropertyGenFlags::NativeBool, RF_Public|RF_Transient|RF_MarkAsNative, nullptr, nullptr, 1, sizeof(bool), sizeof(mineprep_eventSetTickRunOnAnyThread_Parms), &Z_Construct_UFunction_Umineprep_SetTickRunOnAnyThread_Statics::NewProp_bRunOnAnyThread_SetBit, METADATA_PARAMS(0, nullptr) };
const UECodeGen_Private::FPropertyParamsBase* const Z_Construct_UFunction_Umineprep_SetTickRunOnAnyThread_Statics::PropPointers[] = {
	(const UECodeGen_Private::FPropertyParamsBase*)&Z_Construct_UFunction_Umineprep_SetTickRunOnAnyThread_Statics::NewProp_Object,
	(const UECodeGen_Private::FPropertyParamsBase*)&Z_Construct_UFunction_Umineprep_SetTickRunOnAnyThread_Statics::NewProp_bRunOnAnyThread,
};
static_assert(UE_ARRAY_COUNT(Z_Construct_UFunction_Umineprep_SetTickRunOnAnyThread_Statics::PropPointers) < 2048);
const UECodeGen_Private::FFunctionParams Z_Construct_UFunction_Umineprep_SetTickRunOnAnyThread_Statics::FuncParams = { (UObject*(*)())Z_Construct_UClass_Umineprep, nullptr, "SetTickRunOnAnyThread", nullptr, nullptr, Z_Construct_UFunction_Umineprep_SetTickRunOnAnyThread_Statics::PropPointers, UE_ARRAY_COUNT(Z_Construct_UFunction_Umineprep_SetTickRunOnAnyThread_Statics::PropPointers), sizeof(Z_Construct_UFunction_Umineprep_SetTickRunOnAnyThread_Statics::mineprep_eventSetTickRunOnAnyThread_Parms), RF_Public|RF_Transient|RF_MarkAsNative, (EFunctionFlags)0x04022401, 0, 0, METADATA_PARAMS(UE_ARRAY_COUNT(Z_Construct_UFunction_Umineprep_SetTickRunOnAnyThread_Statics::Function_MetaDataParams), Z_Construct_UFunction_Umineprep_SetTickRunOnAnyThread_Statics::Function_MetaDataParams) };
static_assert(sizeof(Z_Construct_UFunction_Umineprep_SetTickRunOnAnyThread_Statics::mineprep_eventSetTickRunOnAnyThread_Parms) < MAX_uint16);
UFunction* Z_Construct_UFunction_Umineprep_SetTickRunOnAnyThread()
{
	static UFunction* ReturnFunction = nullptr;
	if (!ReturnFunction)
	{
		UECodeGen_Private::ConstructUFunction(&ReturnFunction, Z_Construct_UFunction_Umineprep_SetTickRunOnAnyThread_Statics::FuncParams);
	}
	return ReturnFunction;
}
DEFINE_FUNCTION(Umineprep::execSetTickRunOnAnyThread)
{
	P_GET_OBJECT(UObject,Z_Param_Object);
	P_GET_UBOOL(Z_Param_bRunOnAnyThread);
	P_FINISH;
	P_NATIVE_BEGIN;
	Umineprep::SetTickRunOnAnyThread(Z_Param_Object,Z_Param_bRunOnAnyThread);
	P_NATIVE_END;
}
// End Class Umineprep Function SetTickRunOnAnyThread

// Begin Class Umineprep
void Umineprep::StaticRegisterNativesUmineprep()
{
	UClass* Class = Umineprep::StaticClass();
	static const FNameNativePtrPair Funcs[] = {
		{ "GetMaterialInfo", &Umineprep::execGetMaterialInfo },
		{ "GetWidgetTextUnderMouse", &Umineprep::execGetWidgetTextUnderMouse },
		{ "SetCameraPreviewSize", &Umineprep::execSetCameraPreviewSize },
		{ "SetEditorUIScale", &Umineprep::execSetEditorUIScale },
		{ "SetPreviewSelectedCameras", &Umineprep::execSetPreviewSelectedCameras },
		{ "SetTickRunOnAnyThread", &Umineprep::execSetTickRunOnAnyThread },
	};
	FNativeFunctionRegistrar::RegisterFunctions(Class, Funcs, UE_ARRAY_COUNT(Funcs));
}
IMPLEMENT_CLASS_NO_AUTO_REGISTRATION(Umineprep);
UClass* Z_Construct_UClass_Umineprep_NoRegister()
{
	return Umineprep::StaticClass();
}
struct Z_Construct_UClass_Umineprep_Statics
{
#if WITH_METADATA
	static constexpr UECodeGen_Private::FMetaDataPairParam Class_MetaDataParams[] = {
		{ "IncludePath", "MineprepBPLibrary.h" },
		{ "ModuleRelativePath", "Public/MineprepBPLibrary.h" },
	};
#endif // WITH_METADATA
	static UObject* (*const DependentSingletons[])();
	static constexpr FClassFunctionLinkInfo FuncInfo[] = {
		{ &Z_Construct_UFunction_Umineprep_GetMaterialInfo, "GetMaterialInfo" }, // 179558862
		{ &Z_Construct_UFunction_Umineprep_GetWidgetTextUnderMouse, "GetWidgetTextUnderMouse" }, // 2417036259
		{ &Z_Construct_UFunction_Umineprep_SetCameraPreviewSize, "SetCameraPreviewSize" }, // 1733107221
		{ &Z_Construct_UFunction_Umineprep_SetEditorUIScale, "SetEditorUIScale" }, // 801178846
		{ &Z_Construct_UFunction_Umineprep_SetPreviewSelectedCameras, "SetPreviewSelectedCameras" }, // 3797438895
		{ &Z_Construct_UFunction_Umineprep_SetTickRunOnAnyThread, "SetTickRunOnAnyThread" }, // 1712685499
	};
	static_assert(UE_ARRAY_COUNT(FuncInfo) < 2048);
	static constexpr FCppClassTypeInfoStatic StaticCppClassTypeInfo = {
		TCppClassTypeTraits<Umineprep>::IsAbstract,
	};
	static const UECodeGen_Private::FClassParams ClassParams;
};
UObject* (*const Z_Construct_UClass_Umineprep_Statics::DependentSingletons[])() = {
	(UObject* (*)())Z_Construct_UClass_UBlueprintFunctionLibrary,
	(UObject* (*)())Z_Construct_UPackage__Script_Mineprep,
};
static_assert(UE_ARRAY_COUNT(Z_Construct_UClass_Umineprep_Statics::DependentSingletons) < 16);
const UECodeGen_Private::FClassParams Z_Construct_UClass_Umineprep_Statics::ClassParams = {
	&Umineprep::StaticClass,
	nullptr,
	&StaticCppClassTypeInfo,
	DependentSingletons,
	FuncInfo,
	nullptr,
	nullptr,
	UE_ARRAY_COUNT(DependentSingletons),
	UE_ARRAY_COUNT(FuncInfo),
	0,
	0,
	0x000000A0u,
	METADATA_PARAMS(UE_ARRAY_COUNT(Z_Construct_UClass_Umineprep_Statics::Class_MetaDataParams), Z_Construct_UClass_Umineprep_Statics::Class_MetaDataParams)
};
UClass* Z_Construct_UClass_Umineprep()
{
	if (!Z_Registration_Info_UClass_Umineprep.OuterSingleton)
	{
		UECodeGen_Private::ConstructUClass(Z_Registration_Info_UClass_Umineprep.OuterSingleton, Z_Construct_UClass_Umineprep_Statics::ClassParams);
	}
	return Z_Registration_Info_UClass_Umineprep.OuterSingleton;
}
template<> MINEPREP_API UClass* StaticClass<Umineprep>()
{
	return Umineprep::StaticClass();
}
DEFINE_VTABLE_PTR_HELPER_CTOR(Umineprep);
Umineprep::~Umineprep() {}
// End Class Umineprep

// Begin Registration
struct Z_CompiledInDeferFile_FID_MCplugin_Plugins_Mineprep_Source_Mineprep_Public_MineprepBPLibrary_h_Statics
{
	static constexpr FClassRegisterCompiledInInfo ClassInfo[] = {
		{ Z_Construct_UClass_Umineprep, Umineprep::StaticClass, TEXT("Umineprep"), &Z_Registration_Info_UClass_Umineprep, CONSTRUCT_RELOAD_VERSION_INFO(FClassReloadVersionInfo, sizeof(Umineprep), 3791972182U) },
	};
};
static FRegisterCompiledInInfo Z_CompiledInDeferFile_FID_MCplugin_Plugins_Mineprep_Source_Mineprep_Public_MineprepBPLibrary_h_1091920938(TEXT("/Script/Mineprep"),
	Z_CompiledInDeferFile_FID_MCplugin_Plugins_Mineprep_Source_Mineprep_Public_MineprepBPLibrary_h_Statics::ClassInfo, UE_ARRAY_COUNT(Z_CompiledInDeferFile_FID_MCplugin_Plugins_Mineprep_Source_Mineprep_Public_MineprepBPLibrary_h_Statics::ClassInfo),
	nullptr, 0,
	nullptr, 0);
// End Registration
PRAGMA_ENABLE_DEPRECATION_WARNINGS
