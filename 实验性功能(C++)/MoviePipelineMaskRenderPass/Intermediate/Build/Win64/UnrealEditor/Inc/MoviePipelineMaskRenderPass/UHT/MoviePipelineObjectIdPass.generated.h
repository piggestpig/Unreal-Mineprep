// Copyright Epic Games, Inc. All Rights Reserved.
/*===========================================================================
	Generated code exported from UnrealHeaderTool.
	DO NOT modify this manually! Edit the corresponding .h files instead!
===========================================================================*/

// IWYU pragma: private, include "MoviePipelineObjectIdPass.h"
#include "UObject/ObjectMacros.h"
#include "UObject/ScriptMacros.h"

PRAGMA_DISABLE_DEPRECATION_WARNINGS
#ifdef MOVIEPIPELINEMASKRENDERPASS_MoviePipelineObjectIdPass_generated_h
#error "MoviePipelineObjectIdPass.generated.h already included, missing '#pragma once' in MoviePipelineObjectIdPass.h"
#endif
#define MOVIEPIPELINEMASKRENDERPASS_MoviePipelineObjectIdPass_generated_h

#define FID_Mineprep_last_0_4_Plugins_MoviePipelineMaskRenderPass_Source_MoviePipelineMaskRenderPass_Private_MoviePipelineObjectIdPass_h_27_INCLASS_NO_PURE_DECLS \
private: \
	static void StaticRegisterNativesUMoviePipelineObjectIdRenderPass(); \
	friend struct Z_Construct_UClass_UMoviePipelineObjectIdRenderPass_Statics; \
public: \
	DECLARE_CLASS(UMoviePipelineObjectIdRenderPass, UMoviePipelineImagePassBase, COMPILED_IN_FLAGS(0), CASTCLASS_None, TEXT("/Script/MoviePipelineMaskRenderPass"), NO_API) \
	DECLARE_SERIALIZER(UMoviePipelineObjectIdRenderPass)


#define FID_Mineprep_last_0_4_Plugins_MoviePipelineMaskRenderPass_Source_MoviePipelineMaskRenderPass_Private_MoviePipelineObjectIdPass_h_27_ENHANCED_CONSTRUCTORS \
private: \
	/** Private move- and copy-constructors, should never be used */ \
	UMoviePipelineObjectIdRenderPass(UMoviePipelineObjectIdRenderPass&&); \
	UMoviePipelineObjectIdRenderPass(const UMoviePipelineObjectIdRenderPass&); \
public: \
	DECLARE_VTABLE_PTR_HELPER_CTOR(NO_API, UMoviePipelineObjectIdRenderPass); \
	DEFINE_VTABLE_PTR_HELPER_CTOR_CALLER(UMoviePipelineObjectIdRenderPass); \
	DEFINE_DEFAULT_CONSTRUCTOR_CALL(UMoviePipelineObjectIdRenderPass) \
	NO_API virtual ~UMoviePipelineObjectIdRenderPass();


#define FID_Mineprep_last_0_4_Plugins_MoviePipelineMaskRenderPass_Source_MoviePipelineMaskRenderPass_Private_MoviePipelineObjectIdPass_h_24_PROLOG
#define FID_Mineprep_last_0_4_Plugins_MoviePipelineMaskRenderPass_Source_MoviePipelineMaskRenderPass_Private_MoviePipelineObjectIdPass_h_27_GENERATED_BODY \
PRAGMA_DISABLE_DEPRECATION_WARNINGS \
public: \
	FID_Mineprep_last_0_4_Plugins_MoviePipelineMaskRenderPass_Source_MoviePipelineMaskRenderPass_Private_MoviePipelineObjectIdPass_h_27_INCLASS_NO_PURE_DECLS \
	FID_Mineprep_last_0_4_Plugins_MoviePipelineMaskRenderPass_Source_MoviePipelineMaskRenderPass_Private_MoviePipelineObjectIdPass_h_27_ENHANCED_CONSTRUCTORS \
private: \
PRAGMA_ENABLE_DEPRECATION_WARNINGS


template<> MOVIEPIPELINEMASKRENDERPASS_API UClass* StaticClass<class UMoviePipelineObjectIdRenderPass>();

#undef CURRENT_FILE_ID
#define CURRENT_FILE_ID FID_Mineprep_last_0_4_Plugins_MoviePipelineMaskRenderPass_Source_MoviePipelineMaskRenderPass_Private_MoviePipelineObjectIdPass_h


#define FOREACH_ENUM_EMOVIEPIPELINEOBJECTIDPASSIDTYPE(op) \
	op(EMoviePipelineObjectIdPassIdType::Full) \
	op(EMoviePipelineObjectIdPassIdType::Material) \
	op(EMoviePipelineObjectIdPassIdType::Actor) \
	op(EMoviePipelineObjectIdPassIdType::ActorWithHierarchy) \
	op(EMoviePipelineObjectIdPassIdType::Folder) \
	op(EMoviePipelineObjectIdPassIdType::Layer) 

enum class EMoviePipelineObjectIdPassIdType : uint8;
template<> struct TIsUEnumClass<EMoviePipelineObjectIdPassIdType> { enum { Value = true }; };
template<> MOVIEPIPELINEMASKRENDERPASS_API UEnum* StaticEnum<EMoviePipelineObjectIdPassIdType>();

PRAGMA_ENABLE_DEPRECATION_WARNINGS
