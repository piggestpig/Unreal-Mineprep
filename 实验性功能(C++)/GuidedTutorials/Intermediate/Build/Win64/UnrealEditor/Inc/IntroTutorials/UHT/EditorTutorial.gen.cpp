// Copyright Epic Games, Inc. All Rights Reserved.
/*===========================================================================
	Generated code exported from UnrealHeaderTool.
	DO NOT modify this manually! Edit the corresponding .h files instead!
===========================================================================*/

#include "UObject/GeneratedCppIncludes.h"
#include "IntroTutorials/Public/EditorTutorial.h"
PRAGMA_DISABLE_DEPRECATION_WARNINGS
void EmptyLinkFunctionForGeneratedCodeEditorTutorial() {}

// Begin Cross Module References
COREUOBJECT_API UClass* Z_Construct_UClass_UObject();
COREUOBJECT_API UClass* Z_Construct_UClass_UObject_NoRegister();
COREUOBJECT_API UScriptStruct* Z_Construct_UScriptStruct_FSoftClassPath();
COREUOBJECT_API UScriptStruct* Z_Construct_UScriptStruct_FSoftObjectPath();
COREUOBJECT_API UScriptStruct* Z_Construct_UScriptStruct_FVector2D();
ENGINE_API UClass* Z_Construct_UClass_AActor_NoRegister();
ENGINE_API UClass* Z_Construct_UClass_UTexture2D_NoRegister();
INTROTUTORIALS_API UClass* Z_Construct_UClass_UEditorTutorial();
INTROTUTORIALS_API UClass* Z_Construct_UClass_UEditorTutorial_NoRegister();
INTROTUTORIALS_API UEnum* Z_Construct_UEnum_IntroTutorials_ETutorialAnchorIdentifier();
INTROTUTORIALS_API UEnum* Z_Construct_UEnum_IntroTutorials_ETutorialContent();
INTROTUTORIALS_API UScriptStruct* Z_Construct_UScriptStruct_FTutorialCategory();
INTROTUTORIALS_API UScriptStruct* Z_Construct_UScriptStruct_FTutorialContent();
INTROTUTORIALS_API UScriptStruct* Z_Construct_UScriptStruct_FTutorialContentAnchor();
INTROTUTORIALS_API UScriptStruct* Z_Construct_UScriptStruct_FTutorialStage();
INTROTUTORIALS_API UScriptStruct* Z_Construct_UScriptStruct_FTutorialWidgetContent();
SLATECORE_API UEnum* Z_Construct_UEnum_SlateCore_EHorizontalAlignment();
SLATECORE_API UEnum* Z_Construct_UEnum_SlateCore_EVerticalAlignment();
UPackage* Z_Construct_UPackage__Script_IntroTutorials();
// End Cross Module References

// Begin Enum ETutorialContent
static FEnumRegistrationInfo Z_Registration_Info_UEnum_ETutorialContent;
static UEnum* ETutorialContent_StaticEnum()
{
	if (!Z_Registration_Info_UEnum_ETutorialContent.OuterSingleton)
	{
		Z_Registration_Info_UEnum_ETutorialContent.OuterSingleton = GetStaticEnum(Z_Construct_UEnum_IntroTutorials_ETutorialContent, (UObject*)Z_Construct_UPackage__Script_IntroTutorials(), TEXT("ETutorialContent"));
	}
	return Z_Registration_Info_UEnum_ETutorialContent.OuterSingleton;
}
template<> INTROTUTORIALS_API UEnum* StaticEnum<ETutorialContent::Type>()
{
	return ETutorialContent_StaticEnum();
}
struct Z_Construct_UEnum_IntroTutorials_ETutorialContent_Statics
{
#if WITH_METADATA
	static constexpr UECodeGen_Private::FMetaDataPairParam Enum_MetaDataParams[] = {
#if !UE_BUILD_SHIPPING
		{ "Comment", "/** The type of tutorial content to display */" },
#endif
		{ "ModuleRelativePath", "Public/EditorTutorial.h" },
		{ "None.Comment", "/** Blank - displays no content */" },
		{ "None.Name", "ETutorialContent::None" },
		{ "None.ToolTip", "Blank - displays no content" },
		{ "RichText.Comment", "/** Rich text content */" },
		{ "RichText.Name", "ETutorialContent::RichText" },
		{ "RichText.ToolTip", "Rich text content" },
		{ "ScriptName", "TutorialContentType" },
		{ "Text.Comment", "/** Plain text content */" },
		{ "Text.Name", "ETutorialContent::Text" },
		{ "Text.ToolTip", "Plain text content" },
#if !UE_BUILD_SHIPPING
		{ "ToolTip", "The type of tutorial content to display" },
#endif
		{ "UDNExcerpt.Comment", "/** Content from a UDN excerpt */" },
		{ "UDNExcerpt.Name", "ETutorialContent::UDNExcerpt" },
		{ "UDNExcerpt.ToolTip", "Content from a UDN excerpt" },
	};
#endif // WITH_METADATA
	static constexpr UECodeGen_Private::FEnumeratorParam Enumerators[] = {
		{ "ETutorialContent::None", (int64)ETutorialContent::None },
		{ "ETutorialContent::Text", (int64)ETutorialContent::Text },
		{ "ETutorialContent::UDNExcerpt", (int64)ETutorialContent::UDNExcerpt },
		{ "ETutorialContent::RichText", (int64)ETutorialContent::RichText },
	};
	static const UECodeGen_Private::FEnumParams EnumParams;
};
const UECodeGen_Private::FEnumParams Z_Construct_UEnum_IntroTutorials_ETutorialContent_Statics::EnumParams = {
	(UObject*(*)())Z_Construct_UPackage__Script_IntroTutorials,
	nullptr,
	"ETutorialContent",
	"ETutorialContent::Type",
	Z_Construct_UEnum_IntroTutorials_ETutorialContent_Statics::Enumerators,
	RF_Public|RF_Transient|RF_MarkAsNative,
	UE_ARRAY_COUNT(Z_Construct_UEnum_IntroTutorials_ETutorialContent_Statics::Enumerators),
	EEnumFlags::None,
	(uint8)UEnum::ECppForm::Namespaced,
	METADATA_PARAMS(UE_ARRAY_COUNT(Z_Construct_UEnum_IntroTutorials_ETutorialContent_Statics::Enum_MetaDataParams), Z_Construct_UEnum_IntroTutorials_ETutorialContent_Statics::Enum_MetaDataParams)
};
UEnum* Z_Construct_UEnum_IntroTutorials_ETutorialContent()
{
	if (!Z_Registration_Info_UEnum_ETutorialContent.InnerSingleton)
	{
		UECodeGen_Private::ConstructUEnum(Z_Registration_Info_UEnum_ETutorialContent.InnerSingleton, Z_Construct_UEnum_IntroTutorials_ETutorialContent_Statics::EnumParams);
	}
	return Z_Registration_Info_UEnum_ETutorialContent.InnerSingleton;
}
// End Enum ETutorialContent

// Begin Enum ETutorialAnchorIdentifier
static FEnumRegistrationInfo Z_Registration_Info_UEnum_ETutorialAnchorIdentifier;
static UEnum* ETutorialAnchorIdentifier_StaticEnum()
{
	if (!Z_Registration_Info_UEnum_ETutorialAnchorIdentifier.OuterSingleton)
	{
		Z_Registration_Info_UEnum_ETutorialAnchorIdentifier.OuterSingleton = GetStaticEnum(Z_Construct_UEnum_IntroTutorials_ETutorialAnchorIdentifier, (UObject*)Z_Construct_UPackage__Script_IntroTutorials(), TEXT("ETutorialAnchorIdentifier"));
	}
	return Z_Registration_Info_UEnum_ETutorialAnchorIdentifier.OuterSingleton;
}
template<> INTROTUTORIALS_API UEnum* StaticEnum<ETutorialAnchorIdentifier::Type>()
{
	return ETutorialAnchorIdentifier_StaticEnum();
}
struct Z_Construct_UEnum_IntroTutorials_ETutorialAnchorIdentifier_Statics
{
#if WITH_METADATA
	static constexpr UECodeGen_Private::FMetaDataPairParam Enum_MetaDataParams[] = {
		{ "Asset.Comment", "/** An asset accessible via the content browser */" },
		{ "Asset.Name", "ETutorialAnchorIdentifier::Asset" },
		{ "Asset.ToolTip", "An asset accessible via the content browser" },
#if !UE_BUILD_SHIPPING
		{ "Comment", "/** The type of tutorial content to display */" },
#endif
		{ "ModuleRelativePath", "Public/EditorTutorial.h" },
		{ "NamedWidget.Comment", "/** Uses a tutorial wrapper widget */" },
		{ "NamedWidget.Name", "ETutorialAnchorIdentifier::NamedWidget" },
		{ "NamedWidget.ToolTip", "Uses a tutorial wrapper widget" },
		{ "None.Comment", "/** No anchor */" },
		{ "None.Name", "ETutorialAnchorIdentifier::None" },
		{ "None.ToolTip", "No anchor" },
#if !UE_BUILD_SHIPPING
		{ "ToolTip", "The type of tutorial content to display" },
#endif
	};
#endif // WITH_METADATA
	static constexpr UECodeGen_Private::FEnumeratorParam Enumerators[] = {
		{ "ETutorialAnchorIdentifier::None", (int64)ETutorialAnchorIdentifier::None },
		{ "ETutorialAnchorIdentifier::NamedWidget", (int64)ETutorialAnchorIdentifier::NamedWidget },
		{ "ETutorialAnchorIdentifier::Asset", (int64)ETutorialAnchorIdentifier::Asset },
	};
	static const UECodeGen_Private::FEnumParams EnumParams;
};
const UECodeGen_Private::FEnumParams Z_Construct_UEnum_IntroTutorials_ETutorialAnchorIdentifier_Statics::EnumParams = {
	(UObject*(*)())Z_Construct_UPackage__Script_IntroTutorials,
	nullptr,
	"ETutorialAnchorIdentifier",
	"ETutorialAnchorIdentifier::Type",
	Z_Construct_UEnum_IntroTutorials_ETutorialAnchorIdentifier_Statics::Enumerators,
	RF_Public|RF_Transient|RF_MarkAsNative,
	UE_ARRAY_COUNT(Z_Construct_UEnum_IntroTutorials_ETutorialAnchorIdentifier_Statics::Enumerators),
	EEnumFlags::None,
	(uint8)UEnum::ECppForm::Namespaced,
	METADATA_PARAMS(UE_ARRAY_COUNT(Z_Construct_UEnum_IntroTutorials_ETutorialAnchorIdentifier_Statics::Enum_MetaDataParams), Z_Construct_UEnum_IntroTutorials_ETutorialAnchorIdentifier_Statics::Enum_MetaDataParams)
};
UEnum* Z_Construct_UEnum_IntroTutorials_ETutorialAnchorIdentifier()
{
	if (!Z_Registration_Info_UEnum_ETutorialAnchorIdentifier.InnerSingleton)
	{
		UECodeGen_Private::ConstructUEnum(Z_Registration_Info_UEnum_ETutorialAnchorIdentifier.InnerSingleton, Z_Construct_UEnum_IntroTutorials_ETutorialAnchorIdentifier_Statics::EnumParams);
	}
	return Z_Registration_Info_UEnum_ETutorialAnchorIdentifier.InnerSingleton;
}
// End Enum ETutorialAnchorIdentifier

// Begin ScriptStruct FTutorialCategory
static FStructRegistrationInfo Z_Registration_Info_UScriptStruct_TutorialCategory;
class UScriptStruct* FTutorialCategory::StaticStruct()
{
	if (!Z_Registration_Info_UScriptStruct_TutorialCategory.OuterSingleton)
	{
		Z_Registration_Info_UScriptStruct_TutorialCategory.OuterSingleton = GetStaticStruct(Z_Construct_UScriptStruct_FTutorialCategory, (UObject*)Z_Construct_UPackage__Script_IntroTutorials(), TEXT("TutorialCategory"));
	}
	return Z_Registration_Info_UScriptStruct_TutorialCategory.OuterSingleton;
}
template<> INTROTUTORIALS_API UScriptStruct* StaticStruct<FTutorialCategory>()
{
	return FTutorialCategory::StaticStruct();
}
struct Z_Construct_UScriptStruct_FTutorialCategory_Statics
{
#if WITH_METADATA
	static constexpr UECodeGen_Private::FMetaDataPairParam Struct_MetaDataParams[] = {
#if !UE_BUILD_SHIPPING
		{ "Comment", "/** Category description */" },
#endif
		{ "ModuleRelativePath", "Public/EditorTutorial.h" },
#if !UE_BUILD_SHIPPING
		{ "ToolTip", "Category description" },
#endif
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_Identifier_MetaData[] = {
		{ "Category", "Content" },
#if !UE_BUILD_SHIPPING
		{ "Comment", "/** Period-separated category name, e.g. \"Editor Quickstart.Level Editor\" */" },
#endif
		{ "ModuleRelativePath", "Public/EditorTutorial.h" },
#if !UE_BUILD_SHIPPING
		{ "ToolTip", "Period-separated category name, e.g. \"Editor Quickstart.Level Editor\"" },
#endif
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_Title_MetaData[] = {
		{ "Category", "Content" },
#if !UE_BUILD_SHIPPING
		{ "Comment", "/** Title of the category */" },
#endif
		{ "ModuleRelativePath", "Public/EditorTutorial.h" },
#if !UE_BUILD_SHIPPING
		{ "ToolTip", "Title of the category" },
#endif
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_SortOrder_MetaData[] = {
#if !UE_BUILD_SHIPPING
		{ "Comment", "/** Sort order, used by the tutorial browser - set in editor game-agnostic INI file */" },
#endif
		{ "ModuleRelativePath", "Public/EditorTutorial.h" },
#if !UE_BUILD_SHIPPING
		{ "ToolTip", "Sort order, used by the tutorial browser - set in editor game-agnostic INI file" },
#endif
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_Description_MetaData[] = {
		{ "Category", "Content" },
#if !UE_BUILD_SHIPPING
		{ "Comment", "/** Localized text to use to describe this category */" },
#endif
		{ "ModuleRelativePath", "Public/EditorTutorial.h" },
		{ "MultiLine", "TRUE" },
#if !UE_BUILD_SHIPPING
		{ "ToolTip", "Localized text to use to describe this category" },
#endif
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_Icon_MetaData[] = {
		{ "Category", "Tutorial" },
#if !UE_BUILD_SHIPPING
		{ "Comment", "/** Icon for this tutorial, used when presented to the user in the tutorial browser. Only used if there isn't a valid texture to use. */" },
#endif
		{ "ModuleRelativePath", "Public/EditorTutorial.h" },
#if !UE_BUILD_SHIPPING
		{ "ToolTip", "Icon for this tutorial, used when presented to the user in the tutorial browser. Only used if there isn't a valid texture to use." },
#endif
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_Texture_MetaData[] = {
		{ "AllowedClasses", "/Script/Engine.Texture2D" },
		{ "Category", "Tutorial" },
#if !UE_BUILD_SHIPPING
		{ "Comment", "/** Texture for this tutorial, used when presented to the user in the tutorial browser. */" },
#endif
		{ "ModuleRelativePath", "Public/EditorTutorial.h" },
#if !UE_BUILD_SHIPPING
		{ "ToolTip", "Texture for this tutorial, used when presented to the user in the tutorial browser." },
#endif
	};
#endif // WITH_METADATA
	static const UECodeGen_Private::FStrPropertyParams NewProp_Identifier;
	static const UECodeGen_Private::FTextPropertyParams NewProp_Title;
	static const UECodeGen_Private::FIntPropertyParams NewProp_SortOrder;
	static const UECodeGen_Private::FTextPropertyParams NewProp_Description;
	static const UECodeGen_Private::FStrPropertyParams NewProp_Icon;
	static const UECodeGen_Private::FStructPropertyParams NewProp_Texture;
	static const UECodeGen_Private::FPropertyParamsBase* const PropPointers[];
	static void* NewStructOps()
	{
		return (UScriptStruct::ICppStructOps*)new UScriptStruct::TCppStructOps<FTutorialCategory>();
	}
	static const UECodeGen_Private::FStructParams StructParams;
};
const UECodeGen_Private::FStrPropertyParams Z_Construct_UScriptStruct_FTutorialCategory_Statics::NewProp_Identifier = { "Identifier", nullptr, (EPropertyFlags)0x0010000000000001, UECodeGen_Private::EPropertyGenFlags::Str, RF_Public|RF_Transient|RF_MarkAsNative, nullptr, nullptr, 1, STRUCT_OFFSET(FTutorialCategory, Identifier), METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_Identifier_MetaData), NewProp_Identifier_MetaData) };
const UECodeGen_Private::FTextPropertyParams Z_Construct_UScriptStruct_FTutorialCategory_Statics::NewProp_Title = { "Title", nullptr, (EPropertyFlags)0x0010000000000001, UECodeGen_Private::EPropertyGenFlags::Text, RF_Public|RF_Transient|RF_MarkAsNative, nullptr, nullptr, 1, STRUCT_OFFSET(FTutorialCategory, Title), METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_Title_MetaData), NewProp_Title_MetaData) };
const UECodeGen_Private::FIntPropertyParams Z_Construct_UScriptStruct_FTutorialCategory_Statics::NewProp_SortOrder = { "SortOrder", nullptr, (EPropertyFlags)0x0010000000000000, UECodeGen_Private::EPropertyGenFlags::Int, RF_Public|RF_Transient|RF_MarkAsNative, nullptr, nullptr, 1, STRUCT_OFFSET(FTutorialCategory, SortOrder), METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_SortOrder_MetaData), NewProp_SortOrder_MetaData) };
const UECodeGen_Private::FTextPropertyParams Z_Construct_UScriptStruct_FTutorialCategory_Statics::NewProp_Description = { "Description", nullptr, (EPropertyFlags)0x0010000000000001, UECodeGen_Private::EPropertyGenFlags::Text, RF_Public|RF_Transient|RF_MarkAsNative, nullptr, nullptr, 1, STRUCT_OFFSET(FTutorialCategory, Description), METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_Description_MetaData), NewProp_Description_MetaData) };
const UECodeGen_Private::FStrPropertyParams Z_Construct_UScriptStruct_FTutorialCategory_Statics::NewProp_Icon = { "Icon", nullptr, (EPropertyFlags)0x0010000000000001, UECodeGen_Private::EPropertyGenFlags::Str, RF_Public|RF_Transient|RF_MarkAsNative, nullptr, nullptr, 1, STRUCT_OFFSET(FTutorialCategory, Icon), METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_Icon_MetaData), NewProp_Icon_MetaData) };
const UECodeGen_Private::FStructPropertyParams Z_Construct_UScriptStruct_FTutorialCategory_Statics::NewProp_Texture = { "Texture", nullptr, (EPropertyFlags)0x0010000000000001, UECodeGen_Private::EPropertyGenFlags::Struct, RF_Public|RF_Transient|RF_MarkAsNative, nullptr, nullptr, 1, STRUCT_OFFSET(FTutorialCategory, Texture), Z_Construct_UScriptStruct_FSoftObjectPath, METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_Texture_MetaData), NewProp_Texture_MetaData) };
const UECodeGen_Private::FPropertyParamsBase* const Z_Construct_UScriptStruct_FTutorialCategory_Statics::PropPointers[] = {
	(const UECodeGen_Private::FPropertyParamsBase*)&Z_Construct_UScriptStruct_FTutorialCategory_Statics::NewProp_Identifier,
	(const UECodeGen_Private::FPropertyParamsBase*)&Z_Construct_UScriptStruct_FTutorialCategory_Statics::NewProp_Title,
	(const UECodeGen_Private::FPropertyParamsBase*)&Z_Construct_UScriptStruct_FTutorialCategory_Statics::NewProp_SortOrder,
	(const UECodeGen_Private::FPropertyParamsBase*)&Z_Construct_UScriptStruct_FTutorialCategory_Statics::NewProp_Description,
	(const UECodeGen_Private::FPropertyParamsBase*)&Z_Construct_UScriptStruct_FTutorialCategory_Statics::NewProp_Icon,
	(const UECodeGen_Private::FPropertyParamsBase*)&Z_Construct_UScriptStruct_FTutorialCategory_Statics::NewProp_Texture,
};
static_assert(UE_ARRAY_COUNT(Z_Construct_UScriptStruct_FTutorialCategory_Statics::PropPointers) < 2048);
const UECodeGen_Private::FStructParams Z_Construct_UScriptStruct_FTutorialCategory_Statics::StructParams = {
	(UObject* (*)())Z_Construct_UPackage__Script_IntroTutorials,
	nullptr,
	&NewStructOps,
	"TutorialCategory",
	Z_Construct_UScriptStruct_FTutorialCategory_Statics::PropPointers,
	UE_ARRAY_COUNT(Z_Construct_UScriptStruct_FTutorialCategory_Statics::PropPointers),
	sizeof(FTutorialCategory),
	alignof(FTutorialCategory),
	RF_Public|RF_Transient|RF_MarkAsNative,
	EStructFlags(0x00000201),
	METADATA_PARAMS(UE_ARRAY_COUNT(Z_Construct_UScriptStruct_FTutorialCategory_Statics::Struct_MetaDataParams), Z_Construct_UScriptStruct_FTutorialCategory_Statics::Struct_MetaDataParams)
};
UScriptStruct* Z_Construct_UScriptStruct_FTutorialCategory()
{
	if (!Z_Registration_Info_UScriptStruct_TutorialCategory.InnerSingleton)
	{
		UECodeGen_Private::ConstructUScriptStruct(Z_Registration_Info_UScriptStruct_TutorialCategory.InnerSingleton, Z_Construct_UScriptStruct_FTutorialCategory_Statics::StructParams);
	}
	return Z_Registration_Info_UScriptStruct_TutorialCategory.InnerSingleton;
}
// End ScriptStruct FTutorialCategory

// Begin ScriptStruct FTutorialContent
static FStructRegistrationInfo Z_Registration_Info_UScriptStruct_TutorialContent;
class UScriptStruct* FTutorialContent::StaticStruct()
{
	if (!Z_Registration_Info_UScriptStruct_TutorialContent.OuterSingleton)
	{
		Z_Registration_Info_UScriptStruct_TutorialContent.OuterSingleton = GetStaticStruct(Z_Construct_UScriptStruct_FTutorialContent, (UObject*)Z_Construct_UPackage__Script_IntroTutorials(), TEXT("TutorialContent"));
	}
	return Z_Registration_Info_UScriptStruct_TutorialContent.OuterSingleton;
}
template<> INTROTUTORIALS_API UScriptStruct* StaticStruct<FTutorialContent>()
{
	return FTutorialContent::StaticStruct();
}
struct Z_Construct_UScriptStruct_FTutorialContent_Statics
{
#if WITH_METADATA
	static constexpr UECodeGen_Private::FMetaDataPairParam Struct_MetaDataParams[] = {
#if !UE_BUILD_SHIPPING
		{ "Comment", "/** Content wrapper */" },
#endif
		{ "ModuleRelativePath", "Public/EditorTutorial.h" },
#if !UE_BUILD_SHIPPING
		{ "ToolTip", "Content wrapper" },
#endif
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_Type_MetaData[] = {
		{ "Category", "Content" },
#if !UE_BUILD_SHIPPING
		{ "Comment", "/** The type of this content */" },
#endif
		{ "ModuleRelativePath", "Public/EditorTutorial.h" },
#if !UE_BUILD_SHIPPING
		{ "ToolTip", "The type of this content" },
#endif
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_Content_MetaData[] = {
		{ "Category", "Content" },
#if !UE_BUILD_SHIPPING
		{ "Comment", "/** Content reference string, path etc. */" },
#endif
		{ "ModuleRelativePath", "Public/EditorTutorial.h" },
#if !UE_BUILD_SHIPPING
		{ "ToolTip", "Content reference string, path etc." },
#endif
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_ExcerptName_MetaData[] = {
		{ "Category", "Content" },
#if !UE_BUILD_SHIPPING
		{ "Comment", "/** Excerpt name for UDN excerpt */" },
#endif
		{ "ModuleRelativePath", "Public/EditorTutorial.h" },
#if !UE_BUILD_SHIPPING
		{ "ToolTip", "Excerpt name for UDN excerpt" },
#endif
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_Text_MetaData[] = {
		{ "Category", "Content" },
#if !UE_BUILD_SHIPPING
		{ "Comment", "/** Localized text to use with this content */" },
#endif
		{ "ModuleRelativePath", "Public/EditorTutorial.h" },
		{ "MultiLine", "TRUE" },
#if !UE_BUILD_SHIPPING
		{ "ToolTip", "Localized text to use with this content" },
#endif
	};
#endif // WITH_METADATA
	static const UECodeGen_Private::FBytePropertyParams NewProp_Type;
	static const UECodeGen_Private::FStrPropertyParams NewProp_Content;
	static const UECodeGen_Private::FStrPropertyParams NewProp_ExcerptName;
	static const UECodeGen_Private::FTextPropertyParams NewProp_Text;
	static const UECodeGen_Private::FPropertyParamsBase* const PropPointers[];
	static void* NewStructOps()
	{
		return (UScriptStruct::ICppStructOps*)new UScriptStruct::TCppStructOps<FTutorialContent>();
	}
	static const UECodeGen_Private::FStructParams StructParams;
};
const UECodeGen_Private::FBytePropertyParams Z_Construct_UScriptStruct_FTutorialContent_Statics::NewProp_Type = { "Type", nullptr, (EPropertyFlags)0x0010000000000001, UECodeGen_Private::EPropertyGenFlags::Byte, RF_Public|RF_Transient|RF_MarkAsNative, nullptr, nullptr, 1, STRUCT_OFFSET(FTutorialContent, Type), Z_Construct_UEnum_IntroTutorials_ETutorialContent, METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_Type_MetaData), NewProp_Type_MetaData) }; // 2277973851
const UECodeGen_Private::FStrPropertyParams Z_Construct_UScriptStruct_FTutorialContent_Statics::NewProp_Content = { "Content", nullptr, (EPropertyFlags)0x0010000000000001, UECodeGen_Private::EPropertyGenFlags::Str, RF_Public|RF_Transient|RF_MarkAsNative, nullptr, nullptr, 1, STRUCT_OFFSET(FTutorialContent, Content), METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_Content_MetaData), NewProp_Content_MetaData) };
const UECodeGen_Private::FStrPropertyParams Z_Construct_UScriptStruct_FTutorialContent_Statics::NewProp_ExcerptName = { "ExcerptName", nullptr, (EPropertyFlags)0x0010000000000001, UECodeGen_Private::EPropertyGenFlags::Str, RF_Public|RF_Transient|RF_MarkAsNative, nullptr, nullptr, 1, STRUCT_OFFSET(FTutorialContent, ExcerptName), METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_ExcerptName_MetaData), NewProp_ExcerptName_MetaData) };
const UECodeGen_Private::FTextPropertyParams Z_Construct_UScriptStruct_FTutorialContent_Statics::NewProp_Text = { "Text", nullptr, (EPropertyFlags)0x0010000000000001, UECodeGen_Private::EPropertyGenFlags::Text, RF_Public|RF_Transient|RF_MarkAsNative, nullptr, nullptr, 1, STRUCT_OFFSET(FTutorialContent, Text), METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_Text_MetaData), NewProp_Text_MetaData) };
const UECodeGen_Private::FPropertyParamsBase* const Z_Construct_UScriptStruct_FTutorialContent_Statics::PropPointers[] = {
	(const UECodeGen_Private::FPropertyParamsBase*)&Z_Construct_UScriptStruct_FTutorialContent_Statics::NewProp_Type,
	(const UECodeGen_Private::FPropertyParamsBase*)&Z_Construct_UScriptStruct_FTutorialContent_Statics::NewProp_Content,
	(const UECodeGen_Private::FPropertyParamsBase*)&Z_Construct_UScriptStruct_FTutorialContent_Statics::NewProp_ExcerptName,
	(const UECodeGen_Private::FPropertyParamsBase*)&Z_Construct_UScriptStruct_FTutorialContent_Statics::NewProp_Text,
};
static_assert(UE_ARRAY_COUNT(Z_Construct_UScriptStruct_FTutorialContent_Statics::PropPointers) < 2048);
const UECodeGen_Private::FStructParams Z_Construct_UScriptStruct_FTutorialContent_Statics::StructParams = {
	(UObject* (*)())Z_Construct_UPackage__Script_IntroTutorials,
	nullptr,
	&NewStructOps,
	"TutorialContent",
	Z_Construct_UScriptStruct_FTutorialContent_Statics::PropPointers,
	UE_ARRAY_COUNT(Z_Construct_UScriptStruct_FTutorialContent_Statics::PropPointers),
	sizeof(FTutorialContent),
	alignof(FTutorialContent),
	RF_Public|RF_Transient|RF_MarkAsNative,
	EStructFlags(0x00000201),
	METADATA_PARAMS(UE_ARRAY_COUNT(Z_Construct_UScriptStruct_FTutorialContent_Statics::Struct_MetaDataParams), Z_Construct_UScriptStruct_FTutorialContent_Statics::Struct_MetaDataParams)
};
UScriptStruct* Z_Construct_UScriptStruct_FTutorialContent()
{
	if (!Z_Registration_Info_UScriptStruct_TutorialContent.InnerSingleton)
	{
		UECodeGen_Private::ConstructUScriptStruct(Z_Registration_Info_UScriptStruct_TutorialContent.InnerSingleton, Z_Construct_UScriptStruct_FTutorialContent_Statics::StructParams);
	}
	return Z_Registration_Info_UScriptStruct_TutorialContent.InnerSingleton;
}
// End ScriptStruct FTutorialContent

// Begin ScriptStruct FTutorialContentAnchor
static FStructRegistrationInfo Z_Registration_Info_UScriptStruct_TutorialContentAnchor;
class UScriptStruct* FTutorialContentAnchor::StaticStruct()
{
	if (!Z_Registration_Info_UScriptStruct_TutorialContentAnchor.OuterSingleton)
	{
		Z_Registration_Info_UScriptStruct_TutorialContentAnchor.OuterSingleton = GetStaticStruct(Z_Construct_UScriptStruct_FTutorialContentAnchor, (UObject*)Z_Construct_UPackage__Script_IntroTutorials(), TEXT("TutorialContentAnchor"));
	}
	return Z_Registration_Info_UScriptStruct_TutorialContentAnchor.OuterSingleton;
}
template<> INTROTUTORIALS_API UScriptStruct* StaticStruct<FTutorialContentAnchor>()
{
	return FTutorialContentAnchor::StaticStruct();
}
struct Z_Construct_UScriptStruct_FTutorialContentAnchor_Statics
{
#if WITH_METADATA
	static constexpr UECodeGen_Private::FMetaDataPairParam Struct_MetaDataParams[] = {
#if !UE_BUILD_SHIPPING
		{ "Comment", "/** A way of identifying something to be highlighted by a tutorial */" },
#endif
		{ "ModuleRelativePath", "Public/EditorTutorial.h" },
#if !UE_BUILD_SHIPPING
		{ "ToolTip", "A way of identifying something to be highlighted by a tutorial" },
#endif
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_Type_MetaData[] = {
		{ "Category", "Anchor" },
		{ "ModuleRelativePath", "Public/EditorTutorial.h" },
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_WrapperIdentifier_MetaData[] = {
		{ "Category", "Anchor" },
#if !UE_BUILD_SHIPPING
		{ "Comment", "/** If widget is in a wrapper widget, this is the wrapper widget name */" },
#endif
		{ "ModuleRelativePath", "Public/EditorTutorial.h" },
#if !UE_BUILD_SHIPPING
		{ "ToolTip", "If widget is in a wrapper widget, this is the wrapper widget name" },
#endif
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_Asset_MetaData[] = {
		{ "Category", "Anchor" },
#if !UE_BUILD_SHIPPING
		{ "Comment", "/** If reference is an asset, we use this to resolve it */" },
#endif
		{ "ModuleRelativePath", "Public/EditorTutorial.h" },
#if !UE_BUILD_SHIPPING
		{ "ToolTip", "If reference is an asset, we use this to resolve it" },
#endif
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_bDrawHighlight_MetaData[] = {
		{ "Category", "Anchor" },
#if !UE_BUILD_SHIPPING
		{ "Comment", "/** Whether to draw an animated highlight around the widget */" },
#endif
		{ "ModuleRelativePath", "Public/EditorTutorial.h" },
#if !UE_BUILD_SHIPPING
		{ "ToolTip", "Whether to draw an animated highlight around the widget" },
#endif
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_TabToFocusOrOpen_MetaData[] = {
		{ "Category", "Anchor" },
#if !UE_BUILD_SHIPPING
		{ "Comment", "/* Tab on which to focus (EG 'My Blueprint' tab). */" },
#endif
		{ "ModuleRelativePath", "Public/EditorTutorial.h" },
#if !UE_BUILD_SHIPPING
		{ "ToolTip", "Tab on which to focus (EG 'My Blueprint' tab)." },
#endif
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_FriendlyName_MetaData[] = {
		{ "Category", "AnchorMeta|FBlueprintGraphNodeMetaData" },
#if !UE_BUILD_SHIPPING
		{ "Comment", "/* User friendly name to display in the dialog */" },
#endif
		{ "ModuleRelativePath", "Public/EditorTutorial.h" },
#if !UE_BUILD_SHIPPING
		{ "ToolTip", "User friendly name to display in the dialog" },
#endif
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_GUIDString_MetaData[] = {
		{ "Category", "AnchorMeta|FBlueprintGraphNodeMetaData" },
#if !UE_BUILD_SHIPPING
		{ "Comment", "/* The GUID string */" },
#endif
		{ "ModuleRelativePath", "Public/EditorTutorial.h" },
#if !UE_BUILD_SHIPPING
		{ "ToolTip", "The GUID string" },
#endif
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_OuterName_MetaData[] = {
		{ "Category", "AnchorMeta|FBlueprintGraphNodeMetaData" },
#if !UE_BUILD_SHIPPING
		{ "Comment", "/* Name of the outer object - should be the blueprint that 'owns' the node */" },
#endif
		{ "ModuleRelativePath", "Public/EditorTutorial.h" },
#if !UE_BUILD_SHIPPING
		{ "ToolTip", "Name of the outer object - should be the blueprint that 'owns' the node" },
#endif
	};
#endif // WITH_METADATA
	static const UECodeGen_Private::FBytePropertyParams NewProp_Type;
	static const UECodeGen_Private::FNamePropertyParams NewProp_WrapperIdentifier;
	static const UECodeGen_Private::FStructPropertyParams NewProp_Asset;
	static void NewProp_bDrawHighlight_SetBit(void* Obj);
	static const UECodeGen_Private::FBoolPropertyParams NewProp_bDrawHighlight;
	static const UECodeGen_Private::FStrPropertyParams NewProp_TabToFocusOrOpen;
	static const UECodeGen_Private::FStrPropertyParams NewProp_FriendlyName;
	static const UECodeGen_Private::FStrPropertyParams NewProp_GUIDString;
	static const UECodeGen_Private::FStrPropertyParams NewProp_OuterName;
	static const UECodeGen_Private::FPropertyParamsBase* const PropPointers[];
	static void* NewStructOps()
	{
		return (UScriptStruct::ICppStructOps*)new UScriptStruct::TCppStructOps<FTutorialContentAnchor>();
	}
	static const UECodeGen_Private::FStructParams StructParams;
};
const UECodeGen_Private::FBytePropertyParams Z_Construct_UScriptStruct_FTutorialContentAnchor_Statics::NewProp_Type = { "Type", nullptr, (EPropertyFlags)0x0010000000000001, UECodeGen_Private::EPropertyGenFlags::Byte, RF_Public|RF_Transient|RF_MarkAsNative, nullptr, nullptr, 1, STRUCT_OFFSET(FTutorialContentAnchor, Type), Z_Construct_UEnum_IntroTutorials_ETutorialAnchorIdentifier, METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_Type_MetaData), NewProp_Type_MetaData) }; // 2570110542
const UECodeGen_Private::FNamePropertyParams Z_Construct_UScriptStruct_FTutorialContentAnchor_Statics::NewProp_WrapperIdentifier = { "WrapperIdentifier", nullptr, (EPropertyFlags)0x0010000000000001, UECodeGen_Private::EPropertyGenFlags::Name, RF_Public|RF_Transient|RF_MarkAsNative, nullptr, nullptr, 1, STRUCT_OFFSET(FTutorialContentAnchor, WrapperIdentifier), METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_WrapperIdentifier_MetaData), NewProp_WrapperIdentifier_MetaData) };
const UECodeGen_Private::FStructPropertyParams Z_Construct_UScriptStruct_FTutorialContentAnchor_Statics::NewProp_Asset = { "Asset", nullptr, (EPropertyFlags)0x0010000000000001, UECodeGen_Private::EPropertyGenFlags::Struct, RF_Public|RF_Transient|RF_MarkAsNative, nullptr, nullptr, 1, STRUCT_OFFSET(FTutorialContentAnchor, Asset), Z_Construct_UScriptStruct_FSoftObjectPath, METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_Asset_MetaData), NewProp_Asset_MetaData) };
void Z_Construct_UScriptStruct_FTutorialContentAnchor_Statics::NewProp_bDrawHighlight_SetBit(void* Obj)
{
	((FTutorialContentAnchor*)Obj)->bDrawHighlight = 1;
}
const UECodeGen_Private::FBoolPropertyParams Z_Construct_UScriptStruct_FTutorialContentAnchor_Statics::NewProp_bDrawHighlight = { "bDrawHighlight", nullptr, (EPropertyFlags)0x0010000000000001, UECodeGen_Private::EPropertyGenFlags::Bool | UECodeGen_Private::EPropertyGenFlags::NativeBool, RF_Public|RF_Transient|RF_MarkAsNative, nullptr, nullptr, 1, sizeof(bool), sizeof(FTutorialContentAnchor), &Z_Construct_UScriptStruct_FTutorialContentAnchor_Statics::NewProp_bDrawHighlight_SetBit, METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_bDrawHighlight_MetaData), NewProp_bDrawHighlight_MetaData) };
const UECodeGen_Private::FStrPropertyParams Z_Construct_UScriptStruct_FTutorialContentAnchor_Statics::NewProp_TabToFocusOrOpen = { "TabToFocusOrOpen", nullptr, (EPropertyFlags)0x0010000000000001, UECodeGen_Private::EPropertyGenFlags::Str, RF_Public|RF_Transient|RF_MarkAsNative, nullptr, nullptr, 1, STRUCT_OFFSET(FTutorialContentAnchor, TabToFocusOrOpen), METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_TabToFocusOrOpen_MetaData), NewProp_TabToFocusOrOpen_MetaData) };
const UECodeGen_Private::FStrPropertyParams Z_Construct_UScriptStruct_FTutorialContentAnchor_Statics::NewProp_FriendlyName = { "FriendlyName", nullptr, (EPropertyFlags)0x0010000000000001, UECodeGen_Private::EPropertyGenFlags::Str, RF_Public|RF_Transient|RF_MarkAsNative, nullptr, nullptr, 1, STRUCT_OFFSET(FTutorialContentAnchor, FriendlyName), METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_FriendlyName_MetaData), NewProp_FriendlyName_MetaData) };
const UECodeGen_Private::FStrPropertyParams Z_Construct_UScriptStruct_FTutorialContentAnchor_Statics::NewProp_GUIDString = { "GUIDString", nullptr, (EPropertyFlags)0x0010000000000001, UECodeGen_Private::EPropertyGenFlags::Str, RF_Public|RF_Transient|RF_MarkAsNative, nullptr, nullptr, 1, STRUCT_OFFSET(FTutorialContentAnchor, GUIDString), METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_GUIDString_MetaData), NewProp_GUIDString_MetaData) };
const UECodeGen_Private::FStrPropertyParams Z_Construct_UScriptStruct_FTutorialContentAnchor_Statics::NewProp_OuterName = { "OuterName", nullptr, (EPropertyFlags)0x0010000000000001, UECodeGen_Private::EPropertyGenFlags::Str, RF_Public|RF_Transient|RF_MarkAsNative, nullptr, nullptr, 1, STRUCT_OFFSET(FTutorialContentAnchor, OuterName), METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_OuterName_MetaData), NewProp_OuterName_MetaData) };
const UECodeGen_Private::FPropertyParamsBase* const Z_Construct_UScriptStruct_FTutorialContentAnchor_Statics::PropPointers[] = {
	(const UECodeGen_Private::FPropertyParamsBase*)&Z_Construct_UScriptStruct_FTutorialContentAnchor_Statics::NewProp_Type,
	(const UECodeGen_Private::FPropertyParamsBase*)&Z_Construct_UScriptStruct_FTutorialContentAnchor_Statics::NewProp_WrapperIdentifier,
	(const UECodeGen_Private::FPropertyParamsBase*)&Z_Construct_UScriptStruct_FTutorialContentAnchor_Statics::NewProp_Asset,
	(const UECodeGen_Private::FPropertyParamsBase*)&Z_Construct_UScriptStruct_FTutorialContentAnchor_Statics::NewProp_bDrawHighlight,
	(const UECodeGen_Private::FPropertyParamsBase*)&Z_Construct_UScriptStruct_FTutorialContentAnchor_Statics::NewProp_TabToFocusOrOpen,
	(const UECodeGen_Private::FPropertyParamsBase*)&Z_Construct_UScriptStruct_FTutorialContentAnchor_Statics::NewProp_FriendlyName,
	(const UECodeGen_Private::FPropertyParamsBase*)&Z_Construct_UScriptStruct_FTutorialContentAnchor_Statics::NewProp_GUIDString,
	(const UECodeGen_Private::FPropertyParamsBase*)&Z_Construct_UScriptStruct_FTutorialContentAnchor_Statics::NewProp_OuterName,
};
static_assert(UE_ARRAY_COUNT(Z_Construct_UScriptStruct_FTutorialContentAnchor_Statics::PropPointers) < 2048);
const UECodeGen_Private::FStructParams Z_Construct_UScriptStruct_FTutorialContentAnchor_Statics::StructParams = {
	(UObject* (*)())Z_Construct_UPackage__Script_IntroTutorials,
	nullptr,
	&NewStructOps,
	"TutorialContentAnchor",
	Z_Construct_UScriptStruct_FTutorialContentAnchor_Statics::PropPointers,
	UE_ARRAY_COUNT(Z_Construct_UScriptStruct_FTutorialContentAnchor_Statics::PropPointers),
	sizeof(FTutorialContentAnchor),
	alignof(FTutorialContentAnchor),
	RF_Public|RF_Transient|RF_MarkAsNative,
	EStructFlags(0x00000201),
	METADATA_PARAMS(UE_ARRAY_COUNT(Z_Construct_UScriptStruct_FTutorialContentAnchor_Statics::Struct_MetaDataParams), Z_Construct_UScriptStruct_FTutorialContentAnchor_Statics::Struct_MetaDataParams)
};
UScriptStruct* Z_Construct_UScriptStruct_FTutorialContentAnchor()
{
	if (!Z_Registration_Info_UScriptStruct_TutorialContentAnchor.InnerSingleton)
	{
		UECodeGen_Private::ConstructUScriptStruct(Z_Registration_Info_UScriptStruct_TutorialContentAnchor.InnerSingleton, Z_Construct_UScriptStruct_FTutorialContentAnchor_Statics::StructParams);
	}
	return Z_Registration_Info_UScriptStruct_TutorialContentAnchor.InnerSingleton;
}
// End ScriptStruct FTutorialContentAnchor

// Begin ScriptStruct FTutorialWidgetContent
static FStructRegistrationInfo Z_Registration_Info_UScriptStruct_TutorialWidgetContent;
class UScriptStruct* FTutorialWidgetContent::StaticStruct()
{
	if (!Z_Registration_Info_UScriptStruct_TutorialWidgetContent.OuterSingleton)
	{
		Z_Registration_Info_UScriptStruct_TutorialWidgetContent.OuterSingleton = GetStaticStruct(Z_Construct_UScriptStruct_FTutorialWidgetContent, (UObject*)Z_Construct_UPackage__Script_IntroTutorials(), TEXT("TutorialWidgetContent"));
	}
	return Z_Registration_Info_UScriptStruct_TutorialWidgetContent.OuterSingleton;
}
template<> INTROTUTORIALS_API UScriptStruct* StaticStruct<FTutorialWidgetContent>()
{
	return FTutorialWidgetContent::StaticStruct();
}
struct Z_Construct_UScriptStruct_FTutorialWidgetContent_Statics
{
#if WITH_METADATA
	static constexpr UECodeGen_Private::FMetaDataPairParam Struct_MetaDataParams[] = {
#if !UE_BUILD_SHIPPING
		{ "Comment", "/** Content that is displayed relative to a widget */" },
#endif
		{ "ModuleRelativePath", "Public/EditorTutorial.h" },
#if !UE_BUILD_SHIPPING
		{ "ToolTip", "Content that is displayed relative to a widget" },
#endif
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_Content_MetaData[] = {
		{ "Category", "Widget" },
#if !UE_BUILD_SHIPPING
		{ "Comment", "/** Content to associate with widget */" },
#endif
		{ "ModuleRelativePath", "Public/EditorTutorial.h" },
#if !UE_BUILD_SHIPPING
		{ "ToolTip", "Content to associate with widget" },
#endif
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_WidgetAnchor_MetaData[] = {
		{ "Category", "Widget" },
#if !UE_BUILD_SHIPPING
		{ "Comment", "/** Anchor for content widget to highlight */" },
#endif
		{ "ModuleRelativePath", "Public/EditorTutorial.h" },
#if !UE_BUILD_SHIPPING
		{ "ToolTip", "Anchor for content widget to highlight" },
#endif
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_HorizontalAlignment_MetaData[] = {
		{ "Category", "Widget" },
		{ "ModuleRelativePath", "Public/EditorTutorial.h" },
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_VerticalAlignment_MetaData[] = {
		{ "Category", "Widget" },
		{ "ModuleRelativePath", "Public/EditorTutorial.h" },
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_Offset_MetaData[] = {
		{ "Category", "Widget" },
#if !UE_BUILD_SHIPPING
		{ "Comment", "/** Custom offset from widget */" },
#endif
		{ "ModuleRelativePath", "Public/EditorTutorial.h" },
#if !UE_BUILD_SHIPPING
		{ "ToolTip", "Custom offset from widget" },
#endif
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_ContentWidth_MetaData[] = {
		{ "Category", "Widget" },
#if !UE_BUILD_SHIPPING
		{ "Comment", "/** Content width - text will be wrapped at this point */" },
#endif
		{ "ModuleRelativePath", "Public/EditorTutorial.h" },
#if !UE_BUILD_SHIPPING
		{ "ToolTip", "Content width - text will be wrapped at this point" },
#endif
		{ "UIMax", "600.0" },
		{ "UIMin", "10.0" },
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_bAutoFocus_MetaData[] = {
		{ "Category", "Anchor" },
#if !UE_BUILD_SHIPPING
		{ "Comment", "/** If this a node that can be focused (EG a blueprint node) should we auto focus on it */" },
#endif
		{ "ModuleRelativePath", "Public/EditorTutorial.h" },
#if !UE_BUILD_SHIPPING
		{ "ToolTip", "If this a node that can be focused (EG a blueprint node) should we auto focus on it" },
#endif
	};
#endif // WITH_METADATA
	static const UECodeGen_Private::FStructPropertyParams NewProp_Content;
	static const UECodeGen_Private::FStructPropertyParams NewProp_WidgetAnchor;
	static const UECodeGen_Private::FBytePropertyParams NewProp_HorizontalAlignment;
	static const UECodeGen_Private::FBytePropertyParams NewProp_VerticalAlignment;
	static const UECodeGen_Private::FStructPropertyParams NewProp_Offset;
	static const UECodeGen_Private::FFloatPropertyParams NewProp_ContentWidth;
	static void NewProp_bAutoFocus_SetBit(void* Obj);
	static const UECodeGen_Private::FBoolPropertyParams NewProp_bAutoFocus;
	static const UECodeGen_Private::FPropertyParamsBase* const PropPointers[];
	static void* NewStructOps()
	{
		return (UScriptStruct::ICppStructOps*)new UScriptStruct::TCppStructOps<FTutorialWidgetContent>();
	}
	static const UECodeGen_Private::FStructParams StructParams;
};
const UECodeGen_Private::FStructPropertyParams Z_Construct_UScriptStruct_FTutorialWidgetContent_Statics::NewProp_Content = { "Content", nullptr, (EPropertyFlags)0x0010000000000001, UECodeGen_Private::EPropertyGenFlags::Struct, RF_Public|RF_Transient|RF_MarkAsNative, nullptr, nullptr, 1, STRUCT_OFFSET(FTutorialWidgetContent, Content), Z_Construct_UScriptStruct_FTutorialContent, METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_Content_MetaData), NewProp_Content_MetaData) }; // 1755353051
const UECodeGen_Private::FStructPropertyParams Z_Construct_UScriptStruct_FTutorialWidgetContent_Statics::NewProp_WidgetAnchor = { "WidgetAnchor", nullptr, (EPropertyFlags)0x0010000000000001, UECodeGen_Private::EPropertyGenFlags::Struct, RF_Public|RF_Transient|RF_MarkAsNative, nullptr, nullptr, 1, STRUCT_OFFSET(FTutorialWidgetContent, WidgetAnchor), Z_Construct_UScriptStruct_FTutorialContentAnchor, METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_WidgetAnchor_MetaData), NewProp_WidgetAnchor_MetaData) }; // 651610786
const UECodeGen_Private::FBytePropertyParams Z_Construct_UScriptStruct_FTutorialWidgetContent_Statics::NewProp_HorizontalAlignment = { "HorizontalAlignment", nullptr, (EPropertyFlags)0x0010040000000001, UECodeGen_Private::EPropertyGenFlags::Byte, RF_Public|RF_Transient|RF_MarkAsNative, nullptr, nullptr, 1, STRUCT_OFFSET(FTutorialWidgetContent, HorizontalAlignment), Z_Construct_UEnum_SlateCore_EHorizontalAlignment, METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_HorizontalAlignment_MetaData), NewProp_HorizontalAlignment_MetaData) }; // 1062133256
const UECodeGen_Private::FBytePropertyParams Z_Construct_UScriptStruct_FTutorialWidgetContent_Statics::NewProp_VerticalAlignment = { "VerticalAlignment", nullptr, (EPropertyFlags)0x0010040000000001, UECodeGen_Private::EPropertyGenFlags::Byte, RF_Public|RF_Transient|RF_MarkAsNative, nullptr, nullptr, 1, STRUCT_OFFSET(FTutorialWidgetContent, VerticalAlignment), Z_Construct_UEnum_SlateCore_EVerticalAlignment, METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_VerticalAlignment_MetaData), NewProp_VerticalAlignment_MetaData) }; // 550775363
const UECodeGen_Private::FStructPropertyParams Z_Construct_UScriptStruct_FTutorialWidgetContent_Statics::NewProp_Offset = { "Offset", nullptr, (EPropertyFlags)0x0010040000000001, UECodeGen_Private::EPropertyGenFlags::Struct, RF_Public|RF_Transient|RF_MarkAsNative, nullptr, nullptr, 1, STRUCT_OFFSET(FTutorialWidgetContent, Offset), Z_Construct_UScriptStruct_FVector2D, METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_Offset_MetaData), NewProp_Offset_MetaData) };
const UECodeGen_Private::FFloatPropertyParams Z_Construct_UScriptStruct_FTutorialWidgetContent_Statics::NewProp_ContentWidth = { "ContentWidth", nullptr, (EPropertyFlags)0x0010040000000001, UECodeGen_Private::EPropertyGenFlags::Float, RF_Public|RF_Transient|RF_MarkAsNative, nullptr, nullptr, 1, STRUCT_OFFSET(FTutorialWidgetContent, ContentWidth), METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_ContentWidth_MetaData), NewProp_ContentWidth_MetaData) };
void Z_Construct_UScriptStruct_FTutorialWidgetContent_Statics::NewProp_bAutoFocus_SetBit(void* Obj)
{
	((FTutorialWidgetContent*)Obj)->bAutoFocus = 1;
}
const UECodeGen_Private::FBoolPropertyParams Z_Construct_UScriptStruct_FTutorialWidgetContent_Statics::NewProp_bAutoFocus = { "bAutoFocus", nullptr, (EPropertyFlags)0x0010000000000001, UECodeGen_Private::EPropertyGenFlags::Bool | UECodeGen_Private::EPropertyGenFlags::NativeBool, RF_Public|RF_Transient|RF_MarkAsNative, nullptr, nullptr, 1, sizeof(bool), sizeof(FTutorialWidgetContent), &Z_Construct_UScriptStruct_FTutorialWidgetContent_Statics::NewProp_bAutoFocus_SetBit, METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_bAutoFocus_MetaData), NewProp_bAutoFocus_MetaData) };
const UECodeGen_Private::FPropertyParamsBase* const Z_Construct_UScriptStruct_FTutorialWidgetContent_Statics::PropPointers[] = {
	(const UECodeGen_Private::FPropertyParamsBase*)&Z_Construct_UScriptStruct_FTutorialWidgetContent_Statics::NewProp_Content,
	(const UECodeGen_Private::FPropertyParamsBase*)&Z_Construct_UScriptStruct_FTutorialWidgetContent_Statics::NewProp_WidgetAnchor,
	(const UECodeGen_Private::FPropertyParamsBase*)&Z_Construct_UScriptStruct_FTutorialWidgetContent_Statics::NewProp_HorizontalAlignment,
	(const UECodeGen_Private::FPropertyParamsBase*)&Z_Construct_UScriptStruct_FTutorialWidgetContent_Statics::NewProp_VerticalAlignment,
	(const UECodeGen_Private::FPropertyParamsBase*)&Z_Construct_UScriptStruct_FTutorialWidgetContent_Statics::NewProp_Offset,
	(const UECodeGen_Private::FPropertyParamsBase*)&Z_Construct_UScriptStruct_FTutorialWidgetContent_Statics::NewProp_ContentWidth,
	(const UECodeGen_Private::FPropertyParamsBase*)&Z_Construct_UScriptStruct_FTutorialWidgetContent_Statics::NewProp_bAutoFocus,
};
static_assert(UE_ARRAY_COUNT(Z_Construct_UScriptStruct_FTutorialWidgetContent_Statics::PropPointers) < 2048);
const UECodeGen_Private::FStructParams Z_Construct_UScriptStruct_FTutorialWidgetContent_Statics::StructParams = {
	(UObject* (*)())Z_Construct_UPackage__Script_IntroTutorials,
	nullptr,
	&NewStructOps,
	"TutorialWidgetContent",
	Z_Construct_UScriptStruct_FTutorialWidgetContent_Statics::PropPointers,
	UE_ARRAY_COUNT(Z_Construct_UScriptStruct_FTutorialWidgetContent_Statics::PropPointers),
	sizeof(FTutorialWidgetContent),
	alignof(FTutorialWidgetContent),
	RF_Public|RF_Transient|RF_MarkAsNative,
	EStructFlags(0x00000201),
	METADATA_PARAMS(UE_ARRAY_COUNT(Z_Construct_UScriptStruct_FTutorialWidgetContent_Statics::Struct_MetaDataParams), Z_Construct_UScriptStruct_FTutorialWidgetContent_Statics::Struct_MetaDataParams)
};
UScriptStruct* Z_Construct_UScriptStruct_FTutorialWidgetContent()
{
	if (!Z_Registration_Info_UScriptStruct_TutorialWidgetContent.InnerSingleton)
	{
		UECodeGen_Private::ConstructUScriptStruct(Z_Registration_Info_UScriptStruct_TutorialWidgetContent.InnerSingleton, Z_Construct_UScriptStruct_FTutorialWidgetContent_Statics::StructParams);
	}
	return Z_Registration_Info_UScriptStruct_TutorialWidgetContent.InnerSingleton;
}
// End ScriptStruct FTutorialWidgetContent

// Begin ScriptStruct FTutorialStage
static FStructRegistrationInfo Z_Registration_Info_UScriptStruct_TutorialStage;
class UScriptStruct* FTutorialStage::StaticStruct()
{
	if (!Z_Registration_Info_UScriptStruct_TutorialStage.OuterSingleton)
	{
		Z_Registration_Info_UScriptStruct_TutorialStage.OuterSingleton = GetStaticStruct(Z_Construct_UScriptStruct_FTutorialStage, (UObject*)Z_Construct_UPackage__Script_IntroTutorials(), TEXT("TutorialStage"));
	}
	return Z_Registration_Info_UScriptStruct_TutorialStage.OuterSingleton;
}
template<> INTROTUTORIALS_API UScriptStruct* StaticStruct<FTutorialStage>()
{
	return FTutorialStage::StaticStruct();
}
struct Z_Construct_UScriptStruct_FTutorialStage_Statics
{
#if WITH_METADATA
	static constexpr UECodeGen_Private::FMetaDataPairParam Struct_MetaDataParams[] = {
#if !UE_BUILD_SHIPPING
		{ "Comment", "/** A single tutorial stage, containing the optional main content & a number of widgets with content attached */" },
#endif
		{ "ModuleRelativePath", "Public/EditorTutorial.h" },
#if !UE_BUILD_SHIPPING
		{ "ToolTip", "A single tutorial stage, containing the optional main content & a number of widgets with content attached" },
#endif
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_Name_MetaData[] = {
		{ "Category", "Stage" },
#if !UE_BUILD_SHIPPING
		{ "Comment", "/** Identifier for this stage */" },
#endif
		{ "ModuleRelativePath", "Public/EditorTutorial.h" },
#if !UE_BUILD_SHIPPING
		{ "ToolTip", "Identifier for this stage" },
#endif
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_Content_MetaData[] = {
		{ "Category", "Stage" },
#if !UE_BUILD_SHIPPING
		{ "Comment", "/** Non-widget-bound content to display in this stage */" },
#endif
		{ "ModuleRelativePath", "Public/EditorTutorial.h" },
#if !UE_BUILD_SHIPPING
		{ "ToolTip", "Non-widget-bound content to display in this stage" },
#endif
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_WidgetContent_MetaData[] = {
		{ "Category", "Stage" },
#if !UE_BUILD_SHIPPING
		{ "Comment", "/** Widget-bound content to display for this stage */" },
#endif
		{ "ModuleRelativePath", "Public/EditorTutorial.h" },
#if !UE_BUILD_SHIPPING
		{ "ToolTip", "Widget-bound content to display for this stage" },
#endif
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_NextButtonText_MetaData[] = {
		{ "Category", "Stage" },
#if !UE_BUILD_SHIPPING
		{ "Comment", "/** Text to display on the next button */" },
#endif
		{ "ModuleRelativePath", "Public/EditorTutorial.h" },
#if !UE_BUILD_SHIPPING
		{ "ToolTip", "Text to display on the next button" },
#endif
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_BackButtonText_MetaData[] = {
		{ "Category", "Stage" },
#if !UE_BUILD_SHIPPING
		{ "Comment", "/** Text to display on the back button */" },
#endif
		{ "ModuleRelativePath", "Public/EditorTutorial.h" },
#if !UE_BUILD_SHIPPING
		{ "ToolTip", "Text to display on the back button" },
#endif
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_PlatformsToTest_MetaData[] = {
		{ "Category", "Stage" },
#if !UE_BUILD_SHIPPING
		{ "Comment", "/** List of platforms to test against. Meaning of test is determined by InvertPlatformTest. */" },
#endif
		{ "ModuleRelativePath", "Public/EditorTutorial.h" },
#if !UE_BUILD_SHIPPING
		{ "ToolTip", "List of platforms to test against. Meaning of test is determined by InvertPlatformTest." },
#endif
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_bInvertPlatformTest_MetaData[] = {
		{ "Category", "Stage" },
#if !UE_BUILD_SHIPPING
		{ "Comment", "/** If false, stage will be skipped if running on any platform in PlatformsToTest. If true, the stage will be if not running on any platform in PlatformsToTest. */" },
#endif
		{ "ModuleRelativePath", "Public/EditorTutorial.h" },
#if !UE_BUILD_SHIPPING
		{ "ToolTip", "If false, stage will be skipped if running on any platform in PlatformsToTest. If true, the stage will be if not running on any platform in PlatformsToTest." },
#endif
	};
#endif // WITH_METADATA
	static const UECodeGen_Private::FNamePropertyParams NewProp_Name;
	static const UECodeGen_Private::FStructPropertyParams NewProp_Content;
	static const UECodeGen_Private::FStructPropertyParams NewProp_WidgetContent_Inner;
	static const UECodeGen_Private::FArrayPropertyParams NewProp_WidgetContent;
	static const UECodeGen_Private::FTextPropertyParams NewProp_NextButtonText;
	static const UECodeGen_Private::FTextPropertyParams NewProp_BackButtonText;
	static const UECodeGen_Private::FStrPropertyParams NewProp_PlatformsToTest_Inner;
	static const UECodeGen_Private::FArrayPropertyParams NewProp_PlatformsToTest;
	static void NewProp_bInvertPlatformTest_SetBit(void* Obj);
	static const UECodeGen_Private::FBoolPropertyParams NewProp_bInvertPlatformTest;
	static const UECodeGen_Private::FPropertyParamsBase* const PropPointers[];
	static void* NewStructOps()
	{
		return (UScriptStruct::ICppStructOps*)new UScriptStruct::TCppStructOps<FTutorialStage>();
	}
	static const UECodeGen_Private::FStructParams StructParams;
};
const UECodeGen_Private::FNamePropertyParams Z_Construct_UScriptStruct_FTutorialStage_Statics::NewProp_Name = { "Name", nullptr, (EPropertyFlags)0x0010000000000001, UECodeGen_Private::EPropertyGenFlags::Name, RF_Public|RF_Transient|RF_MarkAsNative, nullptr, nullptr, 1, STRUCT_OFFSET(FTutorialStage, Name), METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_Name_MetaData), NewProp_Name_MetaData) };
const UECodeGen_Private::FStructPropertyParams Z_Construct_UScriptStruct_FTutorialStage_Statics::NewProp_Content = { "Content", nullptr, (EPropertyFlags)0x0010000000000001, UECodeGen_Private::EPropertyGenFlags::Struct, RF_Public|RF_Transient|RF_MarkAsNative, nullptr, nullptr, 1, STRUCT_OFFSET(FTutorialStage, Content), Z_Construct_UScriptStruct_FTutorialContent, METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_Content_MetaData), NewProp_Content_MetaData) }; // 1755353051
const UECodeGen_Private::FStructPropertyParams Z_Construct_UScriptStruct_FTutorialStage_Statics::NewProp_WidgetContent_Inner = { "WidgetContent", nullptr, (EPropertyFlags)0x0000000000000000, UECodeGen_Private::EPropertyGenFlags::Struct, RF_Public|RF_Transient|RF_MarkAsNative, nullptr, nullptr, 1, 0, Z_Construct_UScriptStruct_FTutorialWidgetContent, METADATA_PARAMS(0, nullptr) }; // 3963414616
const UECodeGen_Private::FArrayPropertyParams Z_Construct_UScriptStruct_FTutorialStage_Statics::NewProp_WidgetContent = { "WidgetContent", nullptr, (EPropertyFlags)0x0010000000000001, UECodeGen_Private::EPropertyGenFlags::Array, RF_Public|RF_Transient|RF_MarkAsNative, nullptr, nullptr, 1, STRUCT_OFFSET(FTutorialStage, WidgetContent), EArrayPropertyFlags::None, METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_WidgetContent_MetaData), NewProp_WidgetContent_MetaData) }; // 3963414616
const UECodeGen_Private::FTextPropertyParams Z_Construct_UScriptStruct_FTutorialStage_Statics::NewProp_NextButtonText = { "NextButtonText", nullptr, (EPropertyFlags)0x0010000000000001, UECodeGen_Private::EPropertyGenFlags::Text, RF_Public|RF_Transient|RF_MarkAsNative, nullptr, nullptr, 1, STRUCT_OFFSET(FTutorialStage, NextButtonText), METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_NextButtonText_MetaData), NewProp_NextButtonText_MetaData) };
const UECodeGen_Private::FTextPropertyParams Z_Construct_UScriptStruct_FTutorialStage_Statics::NewProp_BackButtonText = { "BackButtonText", nullptr, (EPropertyFlags)0x0010000000000001, UECodeGen_Private::EPropertyGenFlags::Text, RF_Public|RF_Transient|RF_MarkAsNative, nullptr, nullptr, 1, STRUCT_OFFSET(FTutorialStage, BackButtonText), METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_BackButtonText_MetaData), NewProp_BackButtonText_MetaData) };
const UECodeGen_Private::FStrPropertyParams Z_Construct_UScriptStruct_FTutorialStage_Statics::NewProp_PlatformsToTest_Inner = { "PlatformsToTest", nullptr, (EPropertyFlags)0x0000000000000000, UECodeGen_Private::EPropertyGenFlags::Str, RF_Public|RF_Transient|RF_MarkAsNative, nullptr, nullptr, 1, 0, METADATA_PARAMS(0, nullptr) };
const UECodeGen_Private::FArrayPropertyParams Z_Construct_UScriptStruct_FTutorialStage_Statics::NewProp_PlatformsToTest = { "PlatformsToTest", nullptr, (EPropertyFlags)0x0010000000000001, UECodeGen_Private::EPropertyGenFlags::Array, RF_Public|RF_Transient|RF_MarkAsNative, nullptr, nullptr, 1, STRUCT_OFFSET(FTutorialStage, PlatformsToTest), EArrayPropertyFlags::None, METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_PlatformsToTest_MetaData), NewProp_PlatformsToTest_MetaData) };
void Z_Construct_UScriptStruct_FTutorialStage_Statics::NewProp_bInvertPlatformTest_SetBit(void* Obj)
{
	((FTutorialStage*)Obj)->bInvertPlatformTest = 1;
}
const UECodeGen_Private::FBoolPropertyParams Z_Construct_UScriptStruct_FTutorialStage_Statics::NewProp_bInvertPlatformTest = { "bInvertPlatformTest", nullptr, (EPropertyFlags)0x0010000000000001, UECodeGen_Private::EPropertyGenFlags::Bool | UECodeGen_Private::EPropertyGenFlags::NativeBool, RF_Public|RF_Transient|RF_MarkAsNative, nullptr, nullptr, 1, sizeof(bool), sizeof(FTutorialStage), &Z_Construct_UScriptStruct_FTutorialStage_Statics::NewProp_bInvertPlatformTest_SetBit, METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_bInvertPlatformTest_MetaData), NewProp_bInvertPlatformTest_MetaData) };
const UECodeGen_Private::FPropertyParamsBase* const Z_Construct_UScriptStruct_FTutorialStage_Statics::PropPointers[] = {
	(const UECodeGen_Private::FPropertyParamsBase*)&Z_Construct_UScriptStruct_FTutorialStage_Statics::NewProp_Name,
	(const UECodeGen_Private::FPropertyParamsBase*)&Z_Construct_UScriptStruct_FTutorialStage_Statics::NewProp_Content,
	(const UECodeGen_Private::FPropertyParamsBase*)&Z_Construct_UScriptStruct_FTutorialStage_Statics::NewProp_WidgetContent_Inner,
	(const UECodeGen_Private::FPropertyParamsBase*)&Z_Construct_UScriptStruct_FTutorialStage_Statics::NewProp_WidgetContent,
	(const UECodeGen_Private::FPropertyParamsBase*)&Z_Construct_UScriptStruct_FTutorialStage_Statics::NewProp_NextButtonText,
	(const UECodeGen_Private::FPropertyParamsBase*)&Z_Construct_UScriptStruct_FTutorialStage_Statics::NewProp_BackButtonText,
	(const UECodeGen_Private::FPropertyParamsBase*)&Z_Construct_UScriptStruct_FTutorialStage_Statics::NewProp_PlatformsToTest_Inner,
	(const UECodeGen_Private::FPropertyParamsBase*)&Z_Construct_UScriptStruct_FTutorialStage_Statics::NewProp_PlatformsToTest,
	(const UECodeGen_Private::FPropertyParamsBase*)&Z_Construct_UScriptStruct_FTutorialStage_Statics::NewProp_bInvertPlatformTest,
};
static_assert(UE_ARRAY_COUNT(Z_Construct_UScriptStruct_FTutorialStage_Statics::PropPointers) < 2048);
const UECodeGen_Private::FStructParams Z_Construct_UScriptStruct_FTutorialStage_Statics::StructParams = {
	(UObject* (*)())Z_Construct_UPackage__Script_IntroTutorials,
	nullptr,
	&NewStructOps,
	"TutorialStage",
	Z_Construct_UScriptStruct_FTutorialStage_Statics::PropPointers,
	UE_ARRAY_COUNT(Z_Construct_UScriptStruct_FTutorialStage_Statics::PropPointers),
	sizeof(FTutorialStage),
	alignof(FTutorialStage),
	RF_Public|RF_Transient|RF_MarkAsNative,
	EStructFlags(0x00000201),
	METADATA_PARAMS(UE_ARRAY_COUNT(Z_Construct_UScriptStruct_FTutorialStage_Statics::Struct_MetaDataParams), Z_Construct_UScriptStruct_FTutorialStage_Statics::Struct_MetaDataParams)
};
UScriptStruct* Z_Construct_UScriptStruct_FTutorialStage()
{
	if (!Z_Registration_Info_UScriptStruct_TutorialStage.InnerSingleton)
	{
		UECodeGen_Private::ConstructUScriptStruct(Z_Registration_Info_UScriptStruct_TutorialStage.InnerSingleton, Z_Construct_UScriptStruct_FTutorialStage_Statics::StructParams);
	}
	return Z_Registration_Info_UScriptStruct_TutorialStage.InnerSingleton;
}
// End ScriptStruct FTutorialStage

// Begin Class UEditorTutorial Function BeginTutorial
struct Z_Construct_UFunction_UEditorTutorial_BeginTutorial_Statics
{
	struct EditorTutorial_eventBeginTutorial_Parms
	{
		UEditorTutorial* TutorialToStart;
		bool bRestart;
	};
#if WITH_METADATA
	static constexpr UECodeGen_Private::FMetaDataPairParam Function_MetaDataParams[] = {
		{ "Category", "Tutorial" },
#if !UE_BUILD_SHIPPING
		{ "Comment", "/** Begin a tutorial. Note that this will end the current tutorial that is in progress, if any */" },
#endif
		{ "ModuleRelativePath", "Public/EditorTutorial.h" },
#if !UE_BUILD_SHIPPING
		{ "ToolTip", "Begin a tutorial. Note that this will end the current tutorial that is in progress, if any" },
#endif
	};
#endif // WITH_METADATA
	static const UECodeGen_Private::FObjectPropertyParams NewProp_TutorialToStart;
	static void NewProp_bRestart_SetBit(void* Obj);
	static const UECodeGen_Private::FBoolPropertyParams NewProp_bRestart;
	static const UECodeGen_Private::FPropertyParamsBase* const PropPointers[];
	static const UECodeGen_Private::FFunctionParams FuncParams;
};
const UECodeGen_Private::FObjectPropertyParams Z_Construct_UFunction_UEditorTutorial_BeginTutorial_Statics::NewProp_TutorialToStart = { "TutorialToStart", nullptr, (EPropertyFlags)0x0010000000000080, UECodeGen_Private::EPropertyGenFlags::Object, RF_Public|RF_Transient|RF_MarkAsNative, nullptr, nullptr, 1, STRUCT_OFFSET(EditorTutorial_eventBeginTutorial_Parms, TutorialToStart), Z_Construct_UClass_UEditorTutorial_NoRegister, METADATA_PARAMS(0, nullptr) };
void Z_Construct_UFunction_UEditorTutorial_BeginTutorial_Statics::NewProp_bRestart_SetBit(void* Obj)
{
	((EditorTutorial_eventBeginTutorial_Parms*)Obj)->bRestart = 1;
}
const UECodeGen_Private::FBoolPropertyParams Z_Construct_UFunction_UEditorTutorial_BeginTutorial_Statics::NewProp_bRestart = { "bRestart", nullptr, (EPropertyFlags)0x0010000000000080, UECodeGen_Private::EPropertyGenFlags::Bool | UECodeGen_Private::EPropertyGenFlags::NativeBool, RF_Public|RF_Transient|RF_MarkAsNative, nullptr, nullptr, 1, sizeof(bool), sizeof(EditorTutorial_eventBeginTutorial_Parms), &Z_Construct_UFunction_UEditorTutorial_BeginTutorial_Statics::NewProp_bRestart_SetBit, METADATA_PARAMS(0, nullptr) };
const UECodeGen_Private::FPropertyParamsBase* const Z_Construct_UFunction_UEditorTutorial_BeginTutorial_Statics::PropPointers[] = {
	(const UECodeGen_Private::FPropertyParamsBase*)&Z_Construct_UFunction_UEditorTutorial_BeginTutorial_Statics::NewProp_TutorialToStart,
	(const UECodeGen_Private::FPropertyParamsBase*)&Z_Construct_UFunction_UEditorTutorial_BeginTutorial_Statics::NewProp_bRestart,
};
static_assert(UE_ARRAY_COUNT(Z_Construct_UFunction_UEditorTutorial_BeginTutorial_Statics::PropPointers) < 2048);
const UECodeGen_Private::FFunctionParams Z_Construct_UFunction_UEditorTutorial_BeginTutorial_Statics::FuncParams = { (UObject*(*)())Z_Construct_UClass_UEditorTutorial, nullptr, "BeginTutorial", nullptr, nullptr, Z_Construct_UFunction_UEditorTutorial_BeginTutorial_Statics::PropPointers, UE_ARRAY_COUNT(Z_Construct_UFunction_UEditorTutorial_BeginTutorial_Statics::PropPointers), sizeof(Z_Construct_UFunction_UEditorTutorial_BeginTutorial_Statics::EditorTutorial_eventBeginTutorial_Parms), RF_Public|RF_Transient|RF_MarkAsNative, (EFunctionFlags)0x04082401, 0, 0, METADATA_PARAMS(UE_ARRAY_COUNT(Z_Construct_UFunction_UEditorTutorial_BeginTutorial_Statics::Function_MetaDataParams), Z_Construct_UFunction_UEditorTutorial_BeginTutorial_Statics::Function_MetaDataParams) };
static_assert(sizeof(Z_Construct_UFunction_UEditorTutorial_BeginTutorial_Statics::EditorTutorial_eventBeginTutorial_Parms) < MAX_uint16);
UFunction* Z_Construct_UFunction_UEditorTutorial_BeginTutorial()
{
	static UFunction* ReturnFunction = nullptr;
	if (!ReturnFunction)
	{
		UECodeGen_Private::ConstructUFunction(&ReturnFunction, Z_Construct_UFunction_UEditorTutorial_BeginTutorial_Statics::FuncParams);
	}
	return ReturnFunction;
}
DEFINE_FUNCTION(UEditorTutorial::execBeginTutorial)
{
	P_GET_OBJECT(UEditorTutorial,Z_Param_TutorialToStart);
	P_GET_UBOOL(Z_Param_bRestart);
	P_FINISH;
	P_NATIVE_BEGIN;
	UEditorTutorial::BeginTutorial(Z_Param_TutorialToStart,Z_Param_bRestart);
	P_NATIVE_END;
}
// End Class UEditorTutorial Function BeginTutorial

// Begin Class UEditorTutorial Function GetActorReference
struct Z_Construct_UFunction_UEditorTutorial_GetActorReference_Statics
{
	struct EditorTutorial_eventGetActorReference_Parms
	{
		FString PathToActor;
		AActor* ReturnValue;
	};
#if WITH_METADATA
	static constexpr UECodeGen_Private::FMetaDataPairParam Function_MetaDataParams[] = {
		{ "Category", "Tutorial" },
#if !UE_BUILD_SHIPPING
		{ "Comment", "/**\n\x09* Attempts to find the actor specified by PathToActor in the current editor world\n\x09* @param\x09PathToActor\x09The path to the actor (e.g. PersistentLevel.PlayerStart)\n\x09* @return\x09""A reference to the actor, or none if it wasn't found\n\x09*/" },
#endif
		{ "ModuleRelativePath", "Public/EditorTutorial.h" },
#if !UE_BUILD_SHIPPING
		{ "ToolTip", "Attempts to find the actor specified by PathToActor in the current editor world\n@param        PathToActor     The path to the actor (e.g. PersistentLevel.PlayerStart)\n@return       A reference to the actor, or none if it wasn't found" },
#endif
	};
#endif // WITH_METADATA
	static const UECodeGen_Private::FStrPropertyParams NewProp_PathToActor;
	static const UECodeGen_Private::FObjectPropertyParams NewProp_ReturnValue;
	static const UECodeGen_Private::FPropertyParamsBase* const PropPointers[];
	static const UECodeGen_Private::FFunctionParams FuncParams;
};
const UECodeGen_Private::FStrPropertyParams Z_Construct_UFunction_UEditorTutorial_GetActorReference_Statics::NewProp_PathToActor = { "PathToActor", nullptr, (EPropertyFlags)0x0010000000000080, UECodeGen_Private::EPropertyGenFlags::Str, RF_Public|RF_Transient|RF_MarkAsNative, nullptr, nullptr, 1, STRUCT_OFFSET(EditorTutorial_eventGetActorReference_Parms, PathToActor), METADATA_PARAMS(0, nullptr) };
const UECodeGen_Private::FObjectPropertyParams Z_Construct_UFunction_UEditorTutorial_GetActorReference_Statics::NewProp_ReturnValue = { "ReturnValue", nullptr, (EPropertyFlags)0x0010000000000580, UECodeGen_Private::EPropertyGenFlags::Object, RF_Public|RF_Transient|RF_MarkAsNative, nullptr, nullptr, 1, STRUCT_OFFSET(EditorTutorial_eventGetActorReference_Parms, ReturnValue), Z_Construct_UClass_AActor_NoRegister, METADATA_PARAMS(0, nullptr) };
const UECodeGen_Private::FPropertyParamsBase* const Z_Construct_UFunction_UEditorTutorial_GetActorReference_Statics::PropPointers[] = {
	(const UECodeGen_Private::FPropertyParamsBase*)&Z_Construct_UFunction_UEditorTutorial_GetActorReference_Statics::NewProp_PathToActor,
	(const UECodeGen_Private::FPropertyParamsBase*)&Z_Construct_UFunction_UEditorTutorial_GetActorReference_Statics::NewProp_ReturnValue,
};
static_assert(UE_ARRAY_COUNT(Z_Construct_UFunction_UEditorTutorial_GetActorReference_Statics::PropPointers) < 2048);
const UECodeGen_Private::FFunctionParams Z_Construct_UFunction_UEditorTutorial_GetActorReference_Statics::FuncParams = { (UObject*(*)())Z_Construct_UClass_UEditorTutorial, nullptr, "GetActorReference", nullptr, nullptr, Z_Construct_UFunction_UEditorTutorial_GetActorReference_Statics::PropPointers, UE_ARRAY_COUNT(Z_Construct_UFunction_UEditorTutorial_GetActorReference_Statics::PropPointers), sizeof(Z_Construct_UFunction_UEditorTutorial_GetActorReference_Statics::EditorTutorial_eventGetActorReference_Parms), RF_Public|RF_Transient|RF_MarkAsNative, (EFunctionFlags)0x14020401, 0, 0, METADATA_PARAMS(UE_ARRAY_COUNT(Z_Construct_UFunction_UEditorTutorial_GetActorReference_Statics::Function_MetaDataParams), Z_Construct_UFunction_UEditorTutorial_GetActorReference_Statics::Function_MetaDataParams) };
static_assert(sizeof(Z_Construct_UFunction_UEditorTutorial_GetActorReference_Statics::EditorTutorial_eventGetActorReference_Parms) < MAX_uint16);
UFunction* Z_Construct_UFunction_UEditorTutorial_GetActorReference()
{
	static UFunction* ReturnFunction = nullptr;
	if (!ReturnFunction)
	{
		UECodeGen_Private::ConstructUFunction(&ReturnFunction, Z_Construct_UFunction_UEditorTutorial_GetActorReference_Statics::FuncParams);
	}
	return ReturnFunction;
}
DEFINE_FUNCTION(UEditorTutorial::execGetActorReference)
{
	P_GET_PROPERTY(FStrProperty,Z_Param_PathToActor);
	P_FINISH;
	P_NATIVE_BEGIN;
	*(AActor**)Z_Param__Result=P_THIS->GetActorReference(Z_Param_PathToActor);
	P_NATIVE_END;
}
// End Class UEditorTutorial Function GetActorReference

// Begin Class UEditorTutorial Function GetEngineFolderVisibilty
struct Z_Construct_UFunction_UEditorTutorial_GetEngineFolderVisibilty_Statics
{
	struct EditorTutorial_eventGetEngineFolderVisibilty_Parms
	{
		bool ReturnValue;
	};
#if WITH_METADATA
	static constexpr UECodeGen_Private::FMetaDataPairParam Function_MetaDataParams[] = {
		{ "Category", "Tutorial" },
#if !UE_BUILD_SHIPPING
		{ "Comment", "/**\n\x09 * Returns the visibility of the engine folder in the content browser\n\x09 */" },
#endif
		{ "ModuleRelativePath", "Public/EditorTutorial.h" },
#if !UE_BUILD_SHIPPING
		{ "ToolTip", "Returns the visibility of the engine folder in the content browser" },
#endif
	};
#endif // WITH_METADATA
	static void NewProp_ReturnValue_SetBit(void* Obj);
	static const UECodeGen_Private::FBoolPropertyParams NewProp_ReturnValue;
	static const UECodeGen_Private::FPropertyParamsBase* const PropPointers[];
	static const UECodeGen_Private::FFunctionParams FuncParams;
};
void Z_Construct_UFunction_UEditorTutorial_GetEngineFolderVisibilty_Statics::NewProp_ReturnValue_SetBit(void* Obj)
{
	((EditorTutorial_eventGetEngineFolderVisibilty_Parms*)Obj)->ReturnValue = 1;
}
const UECodeGen_Private::FBoolPropertyParams Z_Construct_UFunction_UEditorTutorial_GetEngineFolderVisibilty_Statics::NewProp_ReturnValue = { "ReturnValue", nullptr, (EPropertyFlags)0x0010000000000580, UECodeGen_Private::EPropertyGenFlags::Bool | UECodeGen_Private::EPropertyGenFlags::NativeBool, RF_Public|RF_Transient|RF_MarkAsNative, nullptr, nullptr, 1, sizeof(bool), sizeof(EditorTutorial_eventGetEngineFolderVisibilty_Parms), &Z_Construct_UFunction_UEditorTutorial_GetEngineFolderVisibilty_Statics::NewProp_ReturnValue_SetBit, METADATA_PARAMS(0, nullptr) };
const UECodeGen_Private::FPropertyParamsBase* const Z_Construct_UFunction_UEditorTutorial_GetEngineFolderVisibilty_Statics::PropPointers[] = {
	(const UECodeGen_Private::FPropertyParamsBase*)&Z_Construct_UFunction_UEditorTutorial_GetEngineFolderVisibilty_Statics::NewProp_ReturnValue,
};
static_assert(UE_ARRAY_COUNT(Z_Construct_UFunction_UEditorTutorial_GetEngineFolderVisibilty_Statics::PropPointers) < 2048);
const UECodeGen_Private::FFunctionParams Z_Construct_UFunction_UEditorTutorial_GetEngineFolderVisibilty_Statics::FuncParams = { (UObject*(*)())Z_Construct_UClass_UEditorTutorial, nullptr, "GetEngineFolderVisibilty", nullptr, nullptr, Z_Construct_UFunction_UEditorTutorial_GetEngineFolderVisibilty_Statics::PropPointers, UE_ARRAY_COUNT(Z_Construct_UFunction_UEditorTutorial_GetEngineFolderVisibilty_Statics::PropPointers), sizeof(Z_Construct_UFunction_UEditorTutorial_GetEngineFolderVisibilty_Statics::EditorTutorial_eventGetEngineFolderVisibilty_Parms), RF_Public|RF_Transient|RF_MarkAsNative, (EFunctionFlags)0x04082401, 0, 0, METADATA_PARAMS(UE_ARRAY_COUNT(Z_Construct_UFunction_UEditorTutorial_GetEngineFolderVisibilty_Statics::Function_MetaDataParams), Z_Construct_UFunction_UEditorTutorial_GetEngineFolderVisibilty_Statics::Function_MetaDataParams) };
static_assert(sizeof(Z_Construct_UFunction_UEditorTutorial_GetEngineFolderVisibilty_Statics::EditorTutorial_eventGetEngineFolderVisibilty_Parms) < MAX_uint16);
UFunction* Z_Construct_UFunction_UEditorTutorial_GetEngineFolderVisibilty()
{
	static UFunction* ReturnFunction = nullptr;
	if (!ReturnFunction)
	{
		UECodeGen_Private::ConstructUFunction(&ReturnFunction, Z_Construct_UFunction_UEditorTutorial_GetEngineFolderVisibilty_Statics::FuncParams);
	}
	return ReturnFunction;
}
DEFINE_FUNCTION(UEditorTutorial::execGetEngineFolderVisibilty)
{
	P_FINISH;
	P_NATIVE_BEGIN;
	*(bool*)Z_Param__Result=UEditorTutorial::GetEngineFolderVisibilty();
	P_NATIVE_END;
}
// End Class UEditorTutorial Function GetEngineFolderVisibilty

// Begin Class UEditorTutorial Function GoToNextTutorialStage
struct Z_Construct_UFunction_UEditorTutorial_GoToNextTutorialStage_Statics
{
#if WITH_METADATA
	static constexpr UECodeGen_Private::FMetaDataPairParam Function_MetaDataParams[] = {
		{ "Category", "Tutorial" },
#if !UE_BUILD_SHIPPING
		{ "Comment", "/** Advance to the next stage of a tutorial */" },
#endif
		{ "ModuleRelativePath", "Public/EditorTutorial.h" },
#if !UE_BUILD_SHIPPING
		{ "ToolTip", "Advance to the next stage of a tutorial" },
#endif
	};
#endif // WITH_METADATA
	static const UECodeGen_Private::FFunctionParams FuncParams;
};
const UECodeGen_Private::FFunctionParams Z_Construct_UFunction_UEditorTutorial_GoToNextTutorialStage_Statics::FuncParams = { (UObject*(*)())Z_Construct_UClass_UEditorTutorial, nullptr, "GoToNextTutorialStage", nullptr, nullptr, nullptr, 0, 0, RF_Public|RF_Transient|RF_MarkAsNative, (EFunctionFlags)0x04082401, 0, 0, METADATA_PARAMS(UE_ARRAY_COUNT(Z_Construct_UFunction_UEditorTutorial_GoToNextTutorialStage_Statics::Function_MetaDataParams), Z_Construct_UFunction_UEditorTutorial_GoToNextTutorialStage_Statics::Function_MetaDataParams) };
UFunction* Z_Construct_UFunction_UEditorTutorial_GoToNextTutorialStage()
{
	static UFunction* ReturnFunction = nullptr;
	if (!ReturnFunction)
	{
		UECodeGen_Private::ConstructUFunction(&ReturnFunction, Z_Construct_UFunction_UEditorTutorial_GoToNextTutorialStage_Statics::FuncParams);
	}
	return ReturnFunction;
}
DEFINE_FUNCTION(UEditorTutorial::execGoToNextTutorialStage)
{
	P_FINISH;
	P_NATIVE_BEGIN;
	UEditorTutorial::GoToNextTutorialStage();
	P_NATIVE_END;
}
// End Class UEditorTutorial Function GoToNextTutorialStage

// Begin Class UEditorTutorial Function GoToPreviousTutorialStage
struct Z_Construct_UFunction_UEditorTutorial_GoToPreviousTutorialStage_Statics
{
#if WITH_METADATA
	static constexpr UECodeGen_Private::FMetaDataPairParam Function_MetaDataParams[] = {
		{ "Category", "Tutorial" },
#if !UE_BUILD_SHIPPING
		{ "Comment", "/** Advance to the previous stage of a tutorial */" },
#endif
		{ "ModuleRelativePath", "Public/EditorTutorial.h" },
#if !UE_BUILD_SHIPPING
		{ "ToolTip", "Advance to the previous stage of a tutorial" },
#endif
	};
#endif // WITH_METADATA
	static const UECodeGen_Private::FFunctionParams FuncParams;
};
const UECodeGen_Private::FFunctionParams Z_Construct_UFunction_UEditorTutorial_GoToPreviousTutorialStage_Statics::FuncParams = { (UObject*(*)())Z_Construct_UClass_UEditorTutorial, nullptr, "GoToPreviousTutorialStage", nullptr, nullptr, nullptr, 0, 0, RF_Public|RF_Transient|RF_MarkAsNative, (EFunctionFlags)0x04082401, 0, 0, METADATA_PARAMS(UE_ARRAY_COUNT(Z_Construct_UFunction_UEditorTutorial_GoToPreviousTutorialStage_Statics::Function_MetaDataParams), Z_Construct_UFunction_UEditorTutorial_GoToPreviousTutorialStage_Statics::Function_MetaDataParams) };
UFunction* Z_Construct_UFunction_UEditorTutorial_GoToPreviousTutorialStage()
{
	static UFunction* ReturnFunction = nullptr;
	if (!ReturnFunction)
	{
		UECodeGen_Private::ConstructUFunction(&ReturnFunction, Z_Construct_UFunction_UEditorTutorial_GoToPreviousTutorialStage_Statics::FuncParams);
	}
	return ReturnFunction;
}
DEFINE_FUNCTION(UEditorTutorial::execGoToPreviousTutorialStage)
{
	P_FINISH;
	P_NATIVE_BEGIN;
	UEditorTutorial::GoToPreviousTutorialStage();
	P_NATIVE_END;
}
// End Class UEditorTutorial Function GoToPreviousTutorialStage

// Begin Class UEditorTutorial Function OnTutorialClosed
static FName NAME_UEditorTutorial_OnTutorialClosed = FName(TEXT("OnTutorialClosed"));
void UEditorTutorial::OnTutorialClosed()
{
	ProcessEvent(FindFunctionChecked(NAME_UEditorTutorial_OnTutorialClosed),NULL);
}
struct Z_Construct_UFunction_UEditorTutorial_OnTutorialClosed_Statics
{
#if WITH_METADATA
	static constexpr UECodeGen_Private::FMetaDataPairParam Function_MetaDataParams[] = {
		{ "Category", "Tutorial" },
#if !UE_BUILD_SHIPPING
		{ "Comment", "/** Event fired when a tutorial is closed */" },
#endif
		{ "ModuleRelativePath", "Public/EditorTutorial.h" },
#if !UE_BUILD_SHIPPING
		{ "ToolTip", "Event fired when a tutorial is closed" },
#endif
	};
#endif // WITH_METADATA
	static const UECodeGen_Private::FFunctionParams FuncParams;
};
const UECodeGen_Private::FFunctionParams Z_Construct_UFunction_UEditorTutorial_OnTutorialClosed_Statics::FuncParams = { (UObject*(*)())Z_Construct_UClass_UEditorTutorial, nullptr, "OnTutorialClosed", nullptr, nullptr, nullptr, 0, 0, RF_Public|RF_Transient|RF_MarkAsNative, (EFunctionFlags)0x08080800, 0, 0, METADATA_PARAMS(UE_ARRAY_COUNT(Z_Construct_UFunction_UEditorTutorial_OnTutorialClosed_Statics::Function_MetaDataParams), Z_Construct_UFunction_UEditorTutorial_OnTutorialClosed_Statics::Function_MetaDataParams) };
UFunction* Z_Construct_UFunction_UEditorTutorial_OnTutorialClosed()
{
	static UFunction* ReturnFunction = nullptr;
	if (!ReturnFunction)
	{
		UECodeGen_Private::ConstructUFunction(&ReturnFunction, Z_Construct_UFunction_UEditorTutorial_OnTutorialClosed_Statics::FuncParams);
	}
	return ReturnFunction;
}
// End Class UEditorTutorial Function OnTutorialClosed

// Begin Class UEditorTutorial Function OnTutorialLaunched
static FName NAME_UEditorTutorial_OnTutorialLaunched = FName(TEXT("OnTutorialLaunched"));
void UEditorTutorial::OnTutorialLaunched()
{
	ProcessEvent(FindFunctionChecked(NAME_UEditorTutorial_OnTutorialLaunched),NULL);
}
struct Z_Construct_UFunction_UEditorTutorial_OnTutorialLaunched_Statics
{
#if WITH_METADATA
	static constexpr UECodeGen_Private::FMetaDataPairParam Function_MetaDataParams[] = {
		{ "Category", "Tutorial" },
#if !UE_BUILD_SHIPPING
		{ "Comment", "/** Event fired when a tutorial is launched */" },
#endif
		{ "ModuleRelativePath", "Public/EditorTutorial.h" },
#if !UE_BUILD_SHIPPING
		{ "ToolTip", "Event fired when a tutorial is launched" },
#endif
	};
#endif // WITH_METADATA
	static const UECodeGen_Private::FFunctionParams FuncParams;
};
const UECodeGen_Private::FFunctionParams Z_Construct_UFunction_UEditorTutorial_OnTutorialLaunched_Statics::FuncParams = { (UObject*(*)())Z_Construct_UClass_UEditorTutorial, nullptr, "OnTutorialLaunched", nullptr, nullptr, nullptr, 0, 0, RF_Public|RF_Transient|RF_MarkAsNative, (EFunctionFlags)0x08080800, 0, 0, METADATA_PARAMS(UE_ARRAY_COUNT(Z_Construct_UFunction_UEditorTutorial_OnTutorialLaunched_Statics::Function_MetaDataParams), Z_Construct_UFunction_UEditorTutorial_OnTutorialLaunched_Statics::Function_MetaDataParams) };
UFunction* Z_Construct_UFunction_UEditorTutorial_OnTutorialLaunched()
{
	static UFunction* ReturnFunction = nullptr;
	if (!ReturnFunction)
	{
		UECodeGen_Private::ConstructUFunction(&ReturnFunction, Z_Construct_UFunction_UEditorTutorial_OnTutorialLaunched_Statics::FuncParams);
	}
	return ReturnFunction;
}
// End Class UEditorTutorial Function OnTutorialLaunched

// Begin Class UEditorTutorial Function OnTutorialStageEnded
struct EditorTutorial_eventOnTutorialStageEnded_Parms
{
	FName StageName;
};
static FName NAME_UEditorTutorial_OnTutorialStageEnded = FName(TEXT("OnTutorialStageEnded"));
void UEditorTutorial::OnTutorialStageEnded(FName StageName)
{
	EditorTutorial_eventOnTutorialStageEnded_Parms Parms;
	Parms.StageName=StageName;
	ProcessEvent(FindFunctionChecked(NAME_UEditorTutorial_OnTutorialStageEnded),&Parms);
}
struct Z_Construct_UFunction_UEditorTutorial_OnTutorialStageEnded_Statics
{
#if WITH_METADATA
	static constexpr UECodeGen_Private::FMetaDataPairParam Function_MetaDataParams[] = {
		{ "Category", "Tutorial" },
#if !UE_BUILD_SHIPPING
		{ "Comment", "/** Event fired when a tutorial stage ends */" },
#endif
		{ "ModuleRelativePath", "Public/EditorTutorial.h" },
#if !UE_BUILD_SHIPPING
		{ "ToolTip", "Event fired when a tutorial stage ends" },
#endif
	};
#endif // WITH_METADATA
	static const UECodeGen_Private::FNamePropertyParams NewProp_StageName;
	static const UECodeGen_Private::FPropertyParamsBase* const PropPointers[];
	static const UECodeGen_Private::FFunctionParams FuncParams;
};
const UECodeGen_Private::FNamePropertyParams Z_Construct_UFunction_UEditorTutorial_OnTutorialStageEnded_Statics::NewProp_StageName = { "StageName", nullptr, (EPropertyFlags)0x0010000000000080, UECodeGen_Private::EPropertyGenFlags::Name, RF_Public|RF_Transient|RF_MarkAsNative, nullptr, nullptr, 1, STRUCT_OFFSET(EditorTutorial_eventOnTutorialStageEnded_Parms, StageName), METADATA_PARAMS(0, nullptr) };
const UECodeGen_Private::FPropertyParamsBase* const Z_Construct_UFunction_UEditorTutorial_OnTutorialStageEnded_Statics::PropPointers[] = {
	(const UECodeGen_Private::FPropertyParamsBase*)&Z_Construct_UFunction_UEditorTutorial_OnTutorialStageEnded_Statics::NewProp_StageName,
};
static_assert(UE_ARRAY_COUNT(Z_Construct_UFunction_UEditorTutorial_OnTutorialStageEnded_Statics::PropPointers) < 2048);
const UECodeGen_Private::FFunctionParams Z_Construct_UFunction_UEditorTutorial_OnTutorialStageEnded_Statics::FuncParams = { (UObject*(*)())Z_Construct_UClass_UEditorTutorial, nullptr, "OnTutorialStageEnded", nullptr, nullptr, Z_Construct_UFunction_UEditorTutorial_OnTutorialStageEnded_Statics::PropPointers, UE_ARRAY_COUNT(Z_Construct_UFunction_UEditorTutorial_OnTutorialStageEnded_Statics::PropPointers), sizeof(EditorTutorial_eventOnTutorialStageEnded_Parms), RF_Public|RF_Transient|RF_MarkAsNative, (EFunctionFlags)0x08080800, 0, 0, METADATA_PARAMS(UE_ARRAY_COUNT(Z_Construct_UFunction_UEditorTutorial_OnTutorialStageEnded_Statics::Function_MetaDataParams), Z_Construct_UFunction_UEditorTutorial_OnTutorialStageEnded_Statics::Function_MetaDataParams) };
static_assert(sizeof(EditorTutorial_eventOnTutorialStageEnded_Parms) < MAX_uint16);
UFunction* Z_Construct_UFunction_UEditorTutorial_OnTutorialStageEnded()
{
	static UFunction* ReturnFunction = nullptr;
	if (!ReturnFunction)
	{
		UECodeGen_Private::ConstructUFunction(&ReturnFunction, Z_Construct_UFunction_UEditorTutorial_OnTutorialStageEnded_Statics::FuncParams);
	}
	return ReturnFunction;
}
// End Class UEditorTutorial Function OnTutorialStageEnded

// Begin Class UEditorTutorial Function OnTutorialStageStarted
struct EditorTutorial_eventOnTutorialStageStarted_Parms
{
	FName StageName;
};
static FName NAME_UEditorTutorial_OnTutorialStageStarted = FName(TEXT("OnTutorialStageStarted"));
void UEditorTutorial::OnTutorialStageStarted(FName StageName)
{
	EditorTutorial_eventOnTutorialStageStarted_Parms Parms;
	Parms.StageName=StageName;
	ProcessEvent(FindFunctionChecked(NAME_UEditorTutorial_OnTutorialStageStarted),&Parms);
}
struct Z_Construct_UFunction_UEditorTutorial_OnTutorialStageStarted_Statics
{
#if WITH_METADATA
	static constexpr UECodeGen_Private::FMetaDataPairParam Function_MetaDataParams[] = {
		{ "Category", "Tutorial" },
#if !UE_BUILD_SHIPPING
		{ "Comment", "/** Event fired when a tutorial stage begins */" },
#endif
		{ "ModuleRelativePath", "Public/EditorTutorial.h" },
#if !UE_BUILD_SHIPPING
		{ "ToolTip", "Event fired when a tutorial stage begins" },
#endif
	};
#endif // WITH_METADATA
	static const UECodeGen_Private::FNamePropertyParams NewProp_StageName;
	static const UECodeGen_Private::FPropertyParamsBase* const PropPointers[];
	static const UECodeGen_Private::FFunctionParams FuncParams;
};
const UECodeGen_Private::FNamePropertyParams Z_Construct_UFunction_UEditorTutorial_OnTutorialStageStarted_Statics::NewProp_StageName = { "StageName", nullptr, (EPropertyFlags)0x0010000000000080, UECodeGen_Private::EPropertyGenFlags::Name, RF_Public|RF_Transient|RF_MarkAsNative, nullptr, nullptr, 1, STRUCT_OFFSET(EditorTutorial_eventOnTutorialStageStarted_Parms, StageName), METADATA_PARAMS(0, nullptr) };
const UECodeGen_Private::FPropertyParamsBase* const Z_Construct_UFunction_UEditorTutorial_OnTutorialStageStarted_Statics::PropPointers[] = {
	(const UECodeGen_Private::FPropertyParamsBase*)&Z_Construct_UFunction_UEditorTutorial_OnTutorialStageStarted_Statics::NewProp_StageName,
};
static_assert(UE_ARRAY_COUNT(Z_Construct_UFunction_UEditorTutorial_OnTutorialStageStarted_Statics::PropPointers) < 2048);
const UECodeGen_Private::FFunctionParams Z_Construct_UFunction_UEditorTutorial_OnTutorialStageStarted_Statics::FuncParams = { (UObject*(*)())Z_Construct_UClass_UEditorTutorial, nullptr, "OnTutorialStageStarted", nullptr, nullptr, Z_Construct_UFunction_UEditorTutorial_OnTutorialStageStarted_Statics::PropPointers, UE_ARRAY_COUNT(Z_Construct_UFunction_UEditorTutorial_OnTutorialStageStarted_Statics::PropPointers), sizeof(EditorTutorial_eventOnTutorialStageStarted_Parms), RF_Public|RF_Transient|RF_MarkAsNative, (EFunctionFlags)0x08080800, 0, 0, METADATA_PARAMS(UE_ARRAY_COUNT(Z_Construct_UFunction_UEditorTutorial_OnTutorialStageStarted_Statics::Function_MetaDataParams), Z_Construct_UFunction_UEditorTutorial_OnTutorialStageStarted_Statics::Function_MetaDataParams) };
static_assert(sizeof(EditorTutorial_eventOnTutorialStageStarted_Parms) < MAX_uint16);
UFunction* Z_Construct_UFunction_UEditorTutorial_OnTutorialStageStarted()
{
	static UFunction* ReturnFunction = nullptr;
	if (!ReturnFunction)
	{
		UECodeGen_Private::ConstructUFunction(&ReturnFunction, Z_Construct_UFunction_UEditorTutorial_OnTutorialStageStarted_Statics::FuncParams);
	}
	return ReturnFunction;
}
// End Class UEditorTutorial Function OnTutorialStageStarted

// Begin Class UEditorTutorial Function OpenAsset
struct Z_Construct_UFunction_UEditorTutorial_OpenAsset_Statics
{
	struct EditorTutorial_eventOpenAsset_Parms
	{
		UObject* Asset;
	};
#if WITH_METADATA
	static constexpr UECodeGen_Private::FMetaDataPairParam Function_MetaDataParams[] = {
		{ "Category", "Tutorial" },
#if !UE_BUILD_SHIPPING
		{ "Comment", "/** \n\x09 * Open an asset for use by a tutorial\n\x09 * @param\x09""Asset\x09The asset to open\n\x09 */" },
#endif
		{ "ModuleRelativePath", "Public/EditorTutorial.h" },
#if !UE_BUILD_SHIPPING
		{ "ToolTip", "Open an asset for use by a tutorial\n@param       Asset   The asset to open" },
#endif
	};
#endif // WITH_METADATA
	static const UECodeGen_Private::FObjectPropertyParams NewProp_Asset;
	static const UECodeGen_Private::FPropertyParamsBase* const PropPointers[];
	static const UECodeGen_Private::FFunctionParams FuncParams;
};
const UECodeGen_Private::FObjectPropertyParams Z_Construct_UFunction_UEditorTutorial_OpenAsset_Statics::NewProp_Asset = { "Asset", nullptr, (EPropertyFlags)0x0010000000000080, UECodeGen_Private::EPropertyGenFlags::Object, RF_Public|RF_Transient|RF_MarkAsNative, nullptr, nullptr, 1, STRUCT_OFFSET(EditorTutorial_eventOpenAsset_Parms, Asset), Z_Construct_UClass_UObject_NoRegister, METADATA_PARAMS(0, nullptr) };
const UECodeGen_Private::FPropertyParamsBase* const Z_Construct_UFunction_UEditorTutorial_OpenAsset_Statics::PropPointers[] = {
	(const UECodeGen_Private::FPropertyParamsBase*)&Z_Construct_UFunction_UEditorTutorial_OpenAsset_Statics::NewProp_Asset,
};
static_assert(UE_ARRAY_COUNT(Z_Construct_UFunction_UEditorTutorial_OpenAsset_Statics::PropPointers) < 2048);
const UECodeGen_Private::FFunctionParams Z_Construct_UFunction_UEditorTutorial_OpenAsset_Statics::FuncParams = { (UObject*(*)())Z_Construct_UClass_UEditorTutorial, nullptr, "OpenAsset", nullptr, nullptr, Z_Construct_UFunction_UEditorTutorial_OpenAsset_Statics::PropPointers, UE_ARRAY_COUNT(Z_Construct_UFunction_UEditorTutorial_OpenAsset_Statics::PropPointers), sizeof(Z_Construct_UFunction_UEditorTutorial_OpenAsset_Statics::EditorTutorial_eventOpenAsset_Parms), RF_Public|RF_Transient|RF_MarkAsNative, (EFunctionFlags)0x04082401, 0, 0, METADATA_PARAMS(UE_ARRAY_COUNT(Z_Construct_UFunction_UEditorTutorial_OpenAsset_Statics::Function_MetaDataParams), Z_Construct_UFunction_UEditorTutorial_OpenAsset_Statics::Function_MetaDataParams) };
static_assert(sizeof(Z_Construct_UFunction_UEditorTutorial_OpenAsset_Statics::EditorTutorial_eventOpenAsset_Parms) < MAX_uint16);
UFunction* Z_Construct_UFunction_UEditorTutorial_OpenAsset()
{
	static UFunction* ReturnFunction = nullptr;
	if (!ReturnFunction)
	{
		UECodeGen_Private::ConstructUFunction(&ReturnFunction, Z_Construct_UFunction_UEditorTutorial_OpenAsset_Statics::FuncParams);
	}
	return ReturnFunction;
}
DEFINE_FUNCTION(UEditorTutorial::execOpenAsset)
{
	P_GET_OBJECT(UObject,Z_Param_Asset);
	P_FINISH;
	P_NATIVE_BEGIN;
	UEditorTutorial::OpenAsset(Z_Param_Asset);
	P_NATIVE_END;
}
// End Class UEditorTutorial Function OpenAsset

// Begin Class UEditorTutorial Function SetEngineFolderVisibilty
struct Z_Construct_UFunction_UEditorTutorial_SetEngineFolderVisibilty_Statics
{
	struct EditorTutorial_eventSetEngineFolderVisibilty_Parms
	{
		bool bNewVisibility;
	};
#if WITH_METADATA
	static constexpr UECodeGen_Private::FMetaDataPairParam Function_MetaDataParams[] = {
		{ "Category", "Tutorial" },
#if !UE_BUILD_SHIPPING
		{ "Comment", "/**\n\x09 * Sets the visibility of the engine folder in the content browser\n\x09 */" },
#endif
		{ "ModuleRelativePath", "Public/EditorTutorial.h" },
#if !UE_BUILD_SHIPPING
		{ "ToolTip", "Sets the visibility of the engine folder in the content browser" },
#endif
	};
#endif // WITH_METADATA
	static void NewProp_bNewVisibility_SetBit(void* Obj);
	static const UECodeGen_Private::FBoolPropertyParams NewProp_bNewVisibility;
	static const UECodeGen_Private::FPropertyParamsBase* const PropPointers[];
	static const UECodeGen_Private::FFunctionParams FuncParams;
};
void Z_Construct_UFunction_UEditorTutorial_SetEngineFolderVisibilty_Statics::NewProp_bNewVisibility_SetBit(void* Obj)
{
	((EditorTutorial_eventSetEngineFolderVisibilty_Parms*)Obj)->bNewVisibility = 1;
}
const UECodeGen_Private::FBoolPropertyParams Z_Construct_UFunction_UEditorTutorial_SetEngineFolderVisibilty_Statics::NewProp_bNewVisibility = { "bNewVisibility", nullptr, (EPropertyFlags)0x0010000000000080, UECodeGen_Private::EPropertyGenFlags::Bool | UECodeGen_Private::EPropertyGenFlags::NativeBool, RF_Public|RF_Transient|RF_MarkAsNative, nullptr, nullptr, 1, sizeof(bool), sizeof(EditorTutorial_eventSetEngineFolderVisibilty_Parms), &Z_Construct_UFunction_UEditorTutorial_SetEngineFolderVisibilty_Statics::NewProp_bNewVisibility_SetBit, METADATA_PARAMS(0, nullptr) };
const UECodeGen_Private::FPropertyParamsBase* const Z_Construct_UFunction_UEditorTutorial_SetEngineFolderVisibilty_Statics::PropPointers[] = {
	(const UECodeGen_Private::FPropertyParamsBase*)&Z_Construct_UFunction_UEditorTutorial_SetEngineFolderVisibilty_Statics::NewProp_bNewVisibility,
};
static_assert(UE_ARRAY_COUNT(Z_Construct_UFunction_UEditorTutorial_SetEngineFolderVisibilty_Statics::PropPointers) < 2048);
const UECodeGen_Private::FFunctionParams Z_Construct_UFunction_UEditorTutorial_SetEngineFolderVisibilty_Statics::FuncParams = { (UObject*(*)())Z_Construct_UClass_UEditorTutorial, nullptr, "SetEngineFolderVisibilty", nullptr, nullptr, Z_Construct_UFunction_UEditorTutorial_SetEngineFolderVisibilty_Statics::PropPointers, UE_ARRAY_COUNT(Z_Construct_UFunction_UEditorTutorial_SetEngineFolderVisibilty_Statics::PropPointers), sizeof(Z_Construct_UFunction_UEditorTutorial_SetEngineFolderVisibilty_Statics::EditorTutorial_eventSetEngineFolderVisibilty_Parms), RF_Public|RF_Transient|RF_MarkAsNative, (EFunctionFlags)0x04082401, 0, 0, METADATA_PARAMS(UE_ARRAY_COUNT(Z_Construct_UFunction_UEditorTutorial_SetEngineFolderVisibilty_Statics::Function_MetaDataParams), Z_Construct_UFunction_UEditorTutorial_SetEngineFolderVisibilty_Statics::Function_MetaDataParams) };
static_assert(sizeof(Z_Construct_UFunction_UEditorTutorial_SetEngineFolderVisibilty_Statics::EditorTutorial_eventSetEngineFolderVisibilty_Parms) < MAX_uint16);
UFunction* Z_Construct_UFunction_UEditorTutorial_SetEngineFolderVisibilty()
{
	static UFunction* ReturnFunction = nullptr;
	if (!ReturnFunction)
	{
		UECodeGen_Private::ConstructUFunction(&ReturnFunction, Z_Construct_UFunction_UEditorTutorial_SetEngineFolderVisibilty_Statics::FuncParams);
	}
	return ReturnFunction;
}
DEFINE_FUNCTION(UEditorTutorial::execSetEngineFolderVisibilty)
{
	P_GET_UBOOL(Z_Param_bNewVisibility);
	P_FINISH;
	P_NATIVE_BEGIN;
	UEditorTutorial::SetEngineFolderVisibilty(Z_Param_bNewVisibility);
	P_NATIVE_END;
}
// End Class UEditorTutorial Function SetEngineFolderVisibilty

// Begin Class UEditorTutorial
void UEditorTutorial::StaticRegisterNativesUEditorTutorial()
{
	UClass* Class = UEditorTutorial::StaticClass();
	static const FNameNativePtrPair Funcs[] = {
		{ "BeginTutorial", &UEditorTutorial::execBeginTutorial },
		{ "GetActorReference", &UEditorTutorial::execGetActorReference },
		{ "GetEngineFolderVisibilty", &UEditorTutorial::execGetEngineFolderVisibilty },
		{ "GoToNextTutorialStage", &UEditorTutorial::execGoToNextTutorialStage },
		{ "GoToPreviousTutorialStage", &UEditorTutorial::execGoToPreviousTutorialStage },
		{ "OpenAsset", &UEditorTutorial::execOpenAsset },
		{ "SetEngineFolderVisibilty", &UEditorTutorial::execSetEngineFolderVisibilty },
	};
	FNativeFunctionRegistrar::RegisterFunctions(Class, Funcs, UE_ARRAY_COUNT(Funcs));
}
IMPLEMENT_CLASS_NO_AUTO_REGISTRATION(UEditorTutorial);
UClass* Z_Construct_UClass_UEditorTutorial_NoRegister()
{
	return UEditorTutorial::StaticClass();
}
struct Z_Construct_UClass_UEditorTutorial_Statics
{
#if WITH_METADATA
	static constexpr UECodeGen_Private::FMetaDataPairParam Class_MetaDataParams[] = {
		{ "BlueprintType", "true" },
#if !UE_BUILD_SHIPPING
		{ "Comment", "/** An asset used to build a stage-by-stage tutorial in the editor */" },
#endif
		{ "HideCategories", "Object" },
		{ "IncludePath", "EditorTutorial.h" },
		{ "IsBlueprintBase", "true" },
		{ "ModuleRelativePath", "Public/EditorTutorial.h" },
#if !UE_BUILD_SHIPPING
		{ "ToolTip", "An asset used to build a stage-by-stage tutorial in the editor" },
#endif
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_Title_MetaData[] = {
		{ "Category", "Tutorial" },
#if !UE_BUILD_SHIPPING
		{ "Comment", "/** Title of this tutorial, used when presented to the user */" },
#endif
		{ "ModuleRelativePath", "Public/EditorTutorial.h" },
#if !UE_BUILD_SHIPPING
		{ "ToolTip", "Title of this tutorial, used when presented to the user" },
#endif
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_SortOrder_MetaData[] = {
		{ "Category", "Tutorial" },
#if !UE_BUILD_SHIPPING
		{ "Comment", "/** Sorting priority, used by the tutorial browser */" },
#endif
		{ "ModuleRelativePath", "Public/EditorTutorial.h" },
#if !UE_BUILD_SHIPPING
		{ "ToolTip", "Sorting priority, used by the tutorial browser" },
#endif
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_Icon_MetaData[] = {
		{ "Category", "Tutorial" },
#if !UE_BUILD_SHIPPING
		{ "Comment", "/** Icon name for this tutorial, used when presented to the user in the tutorial browser. This is a name for the icon in the Slate editor style. Only used if there isn't a valid texture to use. */" },
#endif
		{ "ModuleRelativePath", "Public/EditorTutorial.h" },
#if !UE_BUILD_SHIPPING
		{ "ToolTip", "Icon name for this tutorial, used when presented to the user in the tutorial browser. This is a name for the icon in the Slate editor style. Only used if there isn't a valid texture to use." },
#endif
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_Texture_MetaData[] = {
		{ "Category", "Tutorial" },
#if !UE_BUILD_SHIPPING
		{ "Comment", "/** Texture for this tutorial, used when presented to the user in the tutorial browser. */" },
#endif
		{ "ModuleRelativePath", "Public/EditorTutorial.h" },
#if !UE_BUILD_SHIPPING
		{ "ToolTip", "Texture for this tutorial, used when presented to the user in the tutorial browser." },
#endif
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_Category_MetaData[] = {
		{ "Category", "Tutorial" },
#if !UE_BUILD_SHIPPING
		{ "Comment", "/** Category of this tutorial, used to organize tutorials when presented to the user */" },
#endif
		{ "ModuleRelativePath", "Public/EditorTutorial.h" },
#if !UE_BUILD_SHIPPING
		{ "ToolTip", "Category of this tutorial, used to organize tutorials when presented to the user" },
#endif
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_SummaryContent_MetaData[] = {
		{ "Category", "Tutorial" },
#if !UE_BUILD_SHIPPING
		{ "Comment", "/** Content to be displayed for this tutorial when presented to the user in summary */" },
#endif
		{ "ModuleRelativePath", "Public/EditorTutorial.h" },
#if !UE_BUILD_SHIPPING
		{ "ToolTip", "Content to be displayed for this tutorial when presented to the user in summary" },
#endif
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_Stages_MetaData[] = {
		{ "Category", "Stages" },
#if !UE_BUILD_SHIPPING
		{ "Comment", "/** The various stages of this tutorial */" },
#endif
		{ "ModuleRelativePath", "Public/EditorTutorial.h" },
#if !UE_BUILD_SHIPPING
		{ "ToolTip", "The various stages of this tutorial" },
#endif
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_PreviousTutorial_MetaData[] = {
		{ "Category", "Tutorial" },
#if !UE_BUILD_SHIPPING
		{ "Comment", "/** Tutorial to optionally chain back to if the \"back\" button is clicked on the first stage */" },
#endif
		{ "MetaClass", "/Script/IntroTutorials.EditorTutorial" },
		{ "ModuleRelativePath", "Public/EditorTutorial.h" },
#if !UE_BUILD_SHIPPING
		{ "ToolTip", "Tutorial to optionally chain back to if the \"back\" button is clicked on the first stage" },
#endif
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_NextTutorial_MetaData[] = {
		{ "Category", "Tutorial" },
#if !UE_BUILD_SHIPPING
		{ "Comment", "/** Tutorial to optionally chain onto after this tutorial completes */" },
#endif
		{ "MetaClass", "/Script/IntroTutorials.EditorTutorial" },
		{ "ModuleRelativePath", "Public/EditorTutorial.h" },
#if !UE_BUILD_SHIPPING
		{ "ToolTip", "Tutorial to optionally chain onto after this tutorial completes" },
#endif
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_bIsStandalone_MetaData[] = {
		{ "Category", "Tutorial" },
#if !UE_BUILD_SHIPPING
		{ "Comment", "/** A standalone tutorial displays no navigation buttons and each content widget has a close button */" },
#endif
		{ "ModuleRelativePath", "Public/EditorTutorial.h" },
#if !UE_BUILD_SHIPPING
		{ "ToolTip", "A standalone tutorial displays no navigation buttons and each content widget has a close button" },
#endif
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_AssetToUse_MetaData[] = {
		{ "Category", "Tutorial" },
#if !UE_BUILD_SHIPPING
		{ "Comment", "/** Asset to open & attach the tutorial to. Non-widget-bound content will appear in the asset's window */" },
#endif
		{ "ModuleRelativePath", "Public/EditorTutorial.h" },
#if !UE_BUILD_SHIPPING
		{ "ToolTip", "Asset to open & attach the tutorial to. Non-widget-bound content will appear in the asset's window" },
#endif
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_ImportPath_MetaData[] = {
#if !UE_BUILD_SHIPPING
		{ "Comment", "/** The path this tutorial was imported from, if any. */" },
#endif
		{ "ModuleRelativePath", "Public/EditorTutorial.h" },
#if !UE_BUILD_SHIPPING
		{ "ToolTip", "The path this tutorial was imported from, if any." },
#endif
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_bHideInBrowser_MetaData[] = {
		{ "Category", "Tutorial" },
#if !UE_BUILD_SHIPPING
		{ "Comment", "/** Hide this tutorial in the tutorials browser */" },
#endif
		{ "ModuleRelativePath", "Public/EditorTutorial.h" },
#if !UE_BUILD_SHIPPING
		{ "ToolTip", "Hide this tutorial in the tutorials browser" },
#endif
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_SearchTags_MetaData[] = {
		{ "Category", "Tutorial" },
#if !UE_BUILD_SHIPPING
		{ "Comment", "/** Comma seperated list of tags the search will use to help find this tutorial  */" },
#endif
		{ "ModuleRelativePath", "Public/EditorTutorial.h" },
#if !UE_BUILD_SHIPPING
		{ "ToolTip", "Comma seperated list of tags the search will use to help find this tutorial" },
#endif
	};
#endif // WITH_METADATA
	static const UECodeGen_Private::FTextPropertyParams NewProp_Title;
	static const UECodeGen_Private::FIntPropertyParams NewProp_SortOrder;
	static const UECodeGen_Private::FStrPropertyParams NewProp_Icon;
	static const UECodeGen_Private::FObjectPropertyParams NewProp_Texture;
	static const UECodeGen_Private::FStrPropertyParams NewProp_Category;
	static const UECodeGen_Private::FStructPropertyParams NewProp_SummaryContent;
	static const UECodeGen_Private::FStructPropertyParams NewProp_Stages_Inner;
	static const UECodeGen_Private::FArrayPropertyParams NewProp_Stages;
	static const UECodeGen_Private::FStructPropertyParams NewProp_PreviousTutorial;
	static const UECodeGen_Private::FStructPropertyParams NewProp_NextTutorial;
	static void NewProp_bIsStandalone_SetBit(void* Obj);
	static const UECodeGen_Private::FBoolPropertyParams NewProp_bIsStandalone;
	static const UECodeGen_Private::FStructPropertyParams NewProp_AssetToUse;
	static const UECodeGen_Private::FStrPropertyParams NewProp_ImportPath;
	static void NewProp_bHideInBrowser_SetBit(void* Obj);
	static const UECodeGen_Private::FBoolPropertyParams NewProp_bHideInBrowser;
	static const UECodeGen_Private::FTextPropertyParams NewProp_SearchTags;
	static const UECodeGen_Private::FPropertyParamsBase* const PropPointers[];
	static UObject* (*const DependentSingletons[])();
	static constexpr FClassFunctionLinkInfo FuncInfo[] = {
		{ &Z_Construct_UFunction_UEditorTutorial_BeginTutorial, "BeginTutorial" }, // 3348774754
		{ &Z_Construct_UFunction_UEditorTutorial_GetActorReference, "GetActorReference" }, // 255762298
		{ &Z_Construct_UFunction_UEditorTutorial_GetEngineFolderVisibilty, "GetEngineFolderVisibilty" }, // 2128998850
		{ &Z_Construct_UFunction_UEditorTutorial_GoToNextTutorialStage, "GoToNextTutorialStage" }, // 1303999715
		{ &Z_Construct_UFunction_UEditorTutorial_GoToPreviousTutorialStage, "GoToPreviousTutorialStage" }, // 14561191
		{ &Z_Construct_UFunction_UEditorTutorial_OnTutorialClosed, "OnTutorialClosed" }, // 118805232
		{ &Z_Construct_UFunction_UEditorTutorial_OnTutorialLaunched, "OnTutorialLaunched" }, // 2615472564
		{ &Z_Construct_UFunction_UEditorTutorial_OnTutorialStageEnded, "OnTutorialStageEnded" }, // 1956385011
		{ &Z_Construct_UFunction_UEditorTutorial_OnTutorialStageStarted, "OnTutorialStageStarted" }, // 654189177
		{ &Z_Construct_UFunction_UEditorTutorial_OpenAsset, "OpenAsset" }, // 315574014
		{ &Z_Construct_UFunction_UEditorTutorial_SetEngineFolderVisibilty, "SetEngineFolderVisibilty" }, // 3238726769
	};
	static_assert(UE_ARRAY_COUNT(FuncInfo) < 2048);
	static constexpr FCppClassTypeInfoStatic StaticCppClassTypeInfo = {
		TCppClassTypeTraits<UEditorTutorial>::IsAbstract,
	};
	static const UECodeGen_Private::FClassParams ClassParams;
};
const UECodeGen_Private::FTextPropertyParams Z_Construct_UClass_UEditorTutorial_Statics::NewProp_Title = { "Title", nullptr, (EPropertyFlags)0x0010010000000001, UECodeGen_Private::EPropertyGenFlags::Text, RF_Public|RF_Transient|RF_MarkAsNative, nullptr, nullptr, 1, STRUCT_OFFSET(UEditorTutorial, Title), METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_Title_MetaData), NewProp_Title_MetaData) };
const UECodeGen_Private::FIntPropertyParams Z_Construct_UClass_UEditorTutorial_Statics::NewProp_SortOrder = { "SortOrder", nullptr, (EPropertyFlags)0x0010000000010015, UECodeGen_Private::EPropertyGenFlags::Int, RF_Public|RF_Transient|RF_MarkAsNative, nullptr, nullptr, 1, STRUCT_OFFSET(UEditorTutorial, SortOrder), METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_SortOrder_MetaData), NewProp_SortOrder_MetaData) };
const UECodeGen_Private::FStrPropertyParams Z_Construct_UClass_UEditorTutorial_Statics::NewProp_Icon = { "Icon", nullptr, (EPropertyFlags)0x0010000000000001, UECodeGen_Private::EPropertyGenFlags::Str, RF_Public|RF_Transient|RF_MarkAsNative, nullptr, nullptr, 1, STRUCT_OFFSET(UEditorTutorial, Icon), METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_Icon_MetaData), NewProp_Icon_MetaData) };
const UECodeGen_Private::FObjectPropertyParams Z_Construct_UClass_UEditorTutorial_Statics::NewProp_Texture = { "Texture", nullptr, (EPropertyFlags)0x0114000000000001, UECodeGen_Private::EPropertyGenFlags::Object | UECodeGen_Private::EPropertyGenFlags::ObjectPtr, RF_Public|RF_Transient|RF_MarkAsNative, nullptr, nullptr, 1, STRUCT_OFFSET(UEditorTutorial, Texture), Z_Construct_UClass_UTexture2D_NoRegister, METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_Texture_MetaData), NewProp_Texture_MetaData) };
const UECodeGen_Private::FStrPropertyParams Z_Construct_UClass_UEditorTutorial_Statics::NewProp_Category = { "Category", nullptr, (EPropertyFlags)0x0010000000000001, UECodeGen_Private::EPropertyGenFlags::Str, RF_Public|RF_Transient|RF_MarkAsNative, nullptr, nullptr, 1, STRUCT_OFFSET(UEditorTutorial, Category), METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_Category_MetaData), NewProp_Category_MetaData) };
const UECodeGen_Private::FStructPropertyParams Z_Construct_UClass_UEditorTutorial_Statics::NewProp_SummaryContent = { "SummaryContent", nullptr, (EPropertyFlags)0x0010000000000001, UECodeGen_Private::EPropertyGenFlags::Struct, RF_Public|RF_Transient|RF_MarkAsNative, nullptr, nullptr, 1, STRUCT_OFFSET(UEditorTutorial, SummaryContent), Z_Construct_UScriptStruct_FTutorialContent, METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_SummaryContent_MetaData), NewProp_SummaryContent_MetaData) }; // 1755353051
const UECodeGen_Private::FStructPropertyParams Z_Construct_UClass_UEditorTutorial_Statics::NewProp_Stages_Inner = { "Stages", nullptr, (EPropertyFlags)0x0000000000000000, UECodeGen_Private::EPropertyGenFlags::Struct, RF_Public|RF_Transient|RF_MarkAsNative, nullptr, nullptr, 1, 0, Z_Construct_UScriptStruct_FTutorialStage, METADATA_PARAMS(0, nullptr) }; // 3800048113
const UECodeGen_Private::FArrayPropertyParams Z_Construct_UClass_UEditorTutorial_Statics::NewProp_Stages = { "Stages", nullptr, (EPropertyFlags)0x0010000000000001, UECodeGen_Private::EPropertyGenFlags::Array, RF_Public|RF_Transient|RF_MarkAsNative, nullptr, nullptr, 1, STRUCT_OFFSET(UEditorTutorial, Stages), EArrayPropertyFlags::None, METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_Stages_MetaData), NewProp_Stages_MetaData) }; // 3800048113
const UECodeGen_Private::FStructPropertyParams Z_Construct_UClass_UEditorTutorial_Statics::NewProp_PreviousTutorial = { "PreviousTutorial", nullptr, (EPropertyFlags)0x0010000000000001, UECodeGen_Private::EPropertyGenFlags::Struct, RF_Public|RF_Transient|RF_MarkAsNative, nullptr, nullptr, 1, STRUCT_OFFSET(UEditorTutorial, PreviousTutorial), Z_Construct_UScriptStruct_FSoftClassPath, METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_PreviousTutorial_MetaData), NewProp_PreviousTutorial_MetaData) };
const UECodeGen_Private::FStructPropertyParams Z_Construct_UClass_UEditorTutorial_Statics::NewProp_NextTutorial = { "NextTutorial", nullptr, (EPropertyFlags)0x0010000000000001, UECodeGen_Private::EPropertyGenFlags::Struct, RF_Public|RF_Transient|RF_MarkAsNative, nullptr, nullptr, 1, STRUCT_OFFSET(UEditorTutorial, NextTutorial), Z_Construct_UScriptStruct_FSoftClassPath, METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_NextTutorial_MetaData), NewProp_NextTutorial_MetaData) };
void Z_Construct_UClass_UEditorTutorial_Statics::NewProp_bIsStandalone_SetBit(void* Obj)
{
	((UEditorTutorial*)Obj)->bIsStandalone = 1;
}
const UECodeGen_Private::FBoolPropertyParams Z_Construct_UClass_UEditorTutorial_Statics::NewProp_bIsStandalone = { "bIsStandalone", nullptr, (EPropertyFlags)0x0010000000000001, UECodeGen_Private::EPropertyGenFlags::Bool | UECodeGen_Private::EPropertyGenFlags::NativeBool, RF_Public|RF_Transient|RF_MarkAsNative, nullptr, nullptr, 1, sizeof(bool), sizeof(UEditorTutorial), &Z_Construct_UClass_UEditorTutorial_Statics::NewProp_bIsStandalone_SetBit, METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_bIsStandalone_MetaData), NewProp_bIsStandalone_MetaData) };
const UECodeGen_Private::FStructPropertyParams Z_Construct_UClass_UEditorTutorial_Statics::NewProp_AssetToUse = { "AssetToUse", nullptr, (EPropertyFlags)0x0010000000000001, UECodeGen_Private::EPropertyGenFlags::Struct, RF_Public|RF_Transient|RF_MarkAsNative, nullptr, nullptr, 1, STRUCT_OFFSET(UEditorTutorial, AssetToUse), Z_Construct_UScriptStruct_FSoftObjectPath, METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_AssetToUse_MetaData), NewProp_AssetToUse_MetaData) };
const UECodeGen_Private::FStrPropertyParams Z_Construct_UClass_UEditorTutorial_Statics::NewProp_ImportPath = { "ImportPath", nullptr, (EPropertyFlags)0x0010000000000000, UECodeGen_Private::EPropertyGenFlags::Str, RF_Public|RF_Transient|RF_MarkAsNative, nullptr, nullptr, 1, STRUCT_OFFSET(UEditorTutorial, ImportPath), METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_ImportPath_MetaData), NewProp_ImportPath_MetaData) };
void Z_Construct_UClass_UEditorTutorial_Statics::NewProp_bHideInBrowser_SetBit(void* Obj)
{
	((UEditorTutorial*)Obj)->bHideInBrowser = 1;
}
const UECodeGen_Private::FBoolPropertyParams Z_Construct_UClass_UEditorTutorial_Statics::NewProp_bHideInBrowser = { "bHideInBrowser", nullptr, (EPropertyFlags)0x0010000000000001, UECodeGen_Private::EPropertyGenFlags::Bool | UECodeGen_Private::EPropertyGenFlags::NativeBool, RF_Public|RF_Transient|RF_MarkAsNative, nullptr, nullptr, 1, sizeof(bool), sizeof(UEditorTutorial), &Z_Construct_UClass_UEditorTutorial_Statics::NewProp_bHideInBrowser_SetBit, METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_bHideInBrowser_MetaData), NewProp_bHideInBrowser_MetaData) };
const UECodeGen_Private::FTextPropertyParams Z_Construct_UClass_UEditorTutorial_Statics::NewProp_SearchTags = { "SearchTags", nullptr, (EPropertyFlags)0x0010010000000001, UECodeGen_Private::EPropertyGenFlags::Text, RF_Public|RF_Transient|RF_MarkAsNative, nullptr, nullptr, 1, STRUCT_OFFSET(UEditorTutorial, SearchTags), METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_SearchTags_MetaData), NewProp_SearchTags_MetaData) };
const UECodeGen_Private::FPropertyParamsBase* const Z_Construct_UClass_UEditorTutorial_Statics::PropPointers[] = {
	(const UECodeGen_Private::FPropertyParamsBase*)&Z_Construct_UClass_UEditorTutorial_Statics::NewProp_Title,
	(const UECodeGen_Private::FPropertyParamsBase*)&Z_Construct_UClass_UEditorTutorial_Statics::NewProp_SortOrder,
	(const UECodeGen_Private::FPropertyParamsBase*)&Z_Construct_UClass_UEditorTutorial_Statics::NewProp_Icon,
	(const UECodeGen_Private::FPropertyParamsBase*)&Z_Construct_UClass_UEditorTutorial_Statics::NewProp_Texture,
	(const UECodeGen_Private::FPropertyParamsBase*)&Z_Construct_UClass_UEditorTutorial_Statics::NewProp_Category,
	(const UECodeGen_Private::FPropertyParamsBase*)&Z_Construct_UClass_UEditorTutorial_Statics::NewProp_SummaryContent,
	(const UECodeGen_Private::FPropertyParamsBase*)&Z_Construct_UClass_UEditorTutorial_Statics::NewProp_Stages_Inner,
	(const UECodeGen_Private::FPropertyParamsBase*)&Z_Construct_UClass_UEditorTutorial_Statics::NewProp_Stages,
	(const UECodeGen_Private::FPropertyParamsBase*)&Z_Construct_UClass_UEditorTutorial_Statics::NewProp_PreviousTutorial,
	(const UECodeGen_Private::FPropertyParamsBase*)&Z_Construct_UClass_UEditorTutorial_Statics::NewProp_NextTutorial,
	(const UECodeGen_Private::FPropertyParamsBase*)&Z_Construct_UClass_UEditorTutorial_Statics::NewProp_bIsStandalone,
	(const UECodeGen_Private::FPropertyParamsBase*)&Z_Construct_UClass_UEditorTutorial_Statics::NewProp_AssetToUse,
	(const UECodeGen_Private::FPropertyParamsBase*)&Z_Construct_UClass_UEditorTutorial_Statics::NewProp_ImportPath,
	(const UECodeGen_Private::FPropertyParamsBase*)&Z_Construct_UClass_UEditorTutorial_Statics::NewProp_bHideInBrowser,
	(const UECodeGen_Private::FPropertyParamsBase*)&Z_Construct_UClass_UEditorTutorial_Statics::NewProp_SearchTags,
};
static_assert(UE_ARRAY_COUNT(Z_Construct_UClass_UEditorTutorial_Statics::PropPointers) < 2048);
UObject* (*const Z_Construct_UClass_UEditorTutorial_Statics::DependentSingletons[])() = {
	(UObject* (*)())Z_Construct_UClass_UObject,
	(UObject* (*)())Z_Construct_UPackage__Script_IntroTutorials,
};
static_assert(UE_ARRAY_COUNT(Z_Construct_UClass_UEditorTutorial_Statics::DependentSingletons) < 16);
const UECodeGen_Private::FClassParams Z_Construct_UClass_UEditorTutorial_Statics::ClassParams = {
	&UEditorTutorial::StaticClass,
	nullptr,
	&StaticCppClassTypeInfo,
	DependentSingletons,
	FuncInfo,
	Z_Construct_UClass_UEditorTutorial_Statics::PropPointers,
	nullptr,
	UE_ARRAY_COUNT(DependentSingletons),
	UE_ARRAY_COUNT(FuncInfo),
	UE_ARRAY_COUNT(Z_Construct_UClass_UEditorTutorial_Statics::PropPointers),
	0,
	0x001010A0u,
	METADATA_PARAMS(UE_ARRAY_COUNT(Z_Construct_UClass_UEditorTutorial_Statics::Class_MetaDataParams), Z_Construct_UClass_UEditorTutorial_Statics::Class_MetaDataParams)
};
UClass* Z_Construct_UClass_UEditorTutorial()
{
	if (!Z_Registration_Info_UClass_UEditorTutorial.OuterSingleton)
	{
		UECodeGen_Private::ConstructUClass(Z_Registration_Info_UClass_UEditorTutorial.OuterSingleton, Z_Construct_UClass_UEditorTutorial_Statics::ClassParams);
	}
	return Z_Registration_Info_UClass_UEditorTutorial.OuterSingleton;
}
template<> INTROTUTORIALS_API UClass* StaticClass<UEditorTutorial>()
{
	return UEditorTutorial::StaticClass();
}
DEFINE_VTABLE_PTR_HELPER_CTOR(UEditorTutorial);
UEditorTutorial::~UEditorTutorial() {}
// End Class UEditorTutorial

// Begin Registration
struct Z_CompiledInDeferFile_FID_Mineprep_last_0_4_Plugins_GuidedTutorials_Source_IntroTutorials_Public_EditorTutorial_h_Statics
{
	static constexpr FEnumRegisterCompiledInInfo EnumInfo[] = {
		{ ETutorialContent_StaticEnum, TEXT("ETutorialContent"), &Z_Registration_Info_UEnum_ETutorialContent, CONSTRUCT_RELOAD_VERSION_INFO(FEnumReloadVersionInfo, 2277973851U) },
		{ ETutorialAnchorIdentifier_StaticEnum, TEXT("ETutorialAnchorIdentifier"), &Z_Registration_Info_UEnum_ETutorialAnchorIdentifier, CONSTRUCT_RELOAD_VERSION_INFO(FEnumReloadVersionInfo, 2570110542U) },
	};
	static constexpr FStructRegisterCompiledInInfo ScriptStructInfo[] = {
		{ FTutorialCategory::StaticStruct, Z_Construct_UScriptStruct_FTutorialCategory_Statics::NewStructOps, TEXT("TutorialCategory"), &Z_Registration_Info_UScriptStruct_TutorialCategory, CONSTRUCT_RELOAD_VERSION_INFO(FStructReloadVersionInfo, sizeof(FTutorialCategory), 3911846307U) },
		{ FTutorialContent::StaticStruct, Z_Construct_UScriptStruct_FTutorialContent_Statics::NewStructOps, TEXT("TutorialContent"), &Z_Registration_Info_UScriptStruct_TutorialContent, CONSTRUCT_RELOAD_VERSION_INFO(FStructReloadVersionInfo, sizeof(FTutorialContent), 1755353051U) },
		{ FTutorialContentAnchor::StaticStruct, Z_Construct_UScriptStruct_FTutorialContentAnchor_Statics::NewStructOps, TEXT("TutorialContentAnchor"), &Z_Registration_Info_UScriptStruct_TutorialContentAnchor, CONSTRUCT_RELOAD_VERSION_INFO(FStructReloadVersionInfo, sizeof(FTutorialContentAnchor), 651610786U) },
		{ FTutorialWidgetContent::StaticStruct, Z_Construct_UScriptStruct_FTutorialWidgetContent_Statics::NewStructOps, TEXT("TutorialWidgetContent"), &Z_Registration_Info_UScriptStruct_TutorialWidgetContent, CONSTRUCT_RELOAD_VERSION_INFO(FStructReloadVersionInfo, sizeof(FTutorialWidgetContent), 3963414616U) },
		{ FTutorialStage::StaticStruct, Z_Construct_UScriptStruct_FTutorialStage_Statics::NewStructOps, TEXT("TutorialStage"), &Z_Registration_Info_UScriptStruct_TutorialStage, CONSTRUCT_RELOAD_VERSION_INFO(FStructReloadVersionInfo, sizeof(FTutorialStage), 3800048113U) },
	};
	static constexpr FClassRegisterCompiledInInfo ClassInfo[] = {
		{ Z_Construct_UClass_UEditorTutorial, UEditorTutorial::StaticClass, TEXT("UEditorTutorial"), &Z_Registration_Info_UClass_UEditorTutorial, CONSTRUCT_RELOAD_VERSION_INFO(FClassReloadVersionInfo, sizeof(UEditorTutorial), 3117005612U) },
	};
};
static FRegisterCompiledInInfo Z_CompiledInDeferFile_FID_Mineprep_last_0_4_Plugins_GuidedTutorials_Source_IntroTutorials_Public_EditorTutorial_h_1656600381(TEXT("/Script/IntroTutorials"),
	Z_CompiledInDeferFile_FID_Mineprep_last_0_4_Plugins_GuidedTutorials_Source_IntroTutorials_Public_EditorTutorial_h_Statics::ClassInfo, UE_ARRAY_COUNT(Z_CompiledInDeferFile_FID_Mineprep_last_0_4_Plugins_GuidedTutorials_Source_IntroTutorials_Public_EditorTutorial_h_Statics::ClassInfo),
	Z_CompiledInDeferFile_FID_Mineprep_last_0_4_Plugins_GuidedTutorials_Source_IntroTutorials_Public_EditorTutorial_h_Statics::ScriptStructInfo, UE_ARRAY_COUNT(Z_CompiledInDeferFile_FID_Mineprep_last_0_4_Plugins_GuidedTutorials_Source_IntroTutorials_Public_EditorTutorial_h_Statics::ScriptStructInfo),
	Z_CompiledInDeferFile_FID_Mineprep_last_0_4_Plugins_GuidedTutorials_Source_IntroTutorials_Public_EditorTutorial_h_Statics::EnumInfo, UE_ARRAY_COUNT(Z_CompiledInDeferFile_FID_Mineprep_last_0_4_Plugins_GuidedTutorials_Source_IntroTutorials_Public_EditorTutorial_h_Statics::EnumInfo));
// End Registration
PRAGMA_ENABLE_DEPRECATION_WARNINGS
