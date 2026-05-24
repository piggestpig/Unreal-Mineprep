// Copyright Epic Games, Inc. All Rights Reserved.

#include "SMaterialDynamicParametersPanelWidget.h"

#include "DetailColumnSizeData.h"
#include "DetailWidgetRow.h"
#include "Styling/AppStyle.h"
#include "IDetailPropertyRow.h"
#include "IDetailTreeNode.h"
#include "IPropertyRowGenerator.h"
#include "PropertyCustomizationHelpers.h"
#include "PropertyEditorModule.h"
#include "PropertyHandle.h"
#include "Framework/MultiBox/MultiBoxBuilder.h"
#include "Framework/MultiBox/MultiBoxDefs.h"
#include "Framework/Application/SlateApplication.h"
#include "Subsystems/AssetEditorSubsystem.h"
#include "ILevelSequenceEditorToolkit.h"
#include "LevelSequence.h"
#include "LevelSequenceEditorBlueprintLibrary.h"
#include "ISequencer.h"
#include "Materials/MaterialInstance.h"
#include "Materials/MaterialInterface.h"
#include "Modules/ModuleManager.h"
#include "MovieScene.h"
#include "UObject/Object.h"
#include "Sections/MovieSceneComponentMaterialParameterSection.h"
#include "Sections/MovieSceneParameterSection.h"
#include "Widgets/Layout/SWidgetSwitcher.h"
#include "Widgets/Text/SInlineEditableTextBlock.h"
#include "Widgets/Views/SExpanderArrow.h"
#include "Widgets/Views/STreeView.h"
// Mineprep: Headers for keyframe functionality
#include "Components/MeshComponent.h"
#include "Engine/Font.h"
#include "EngineUtils.h"
#include "Tracks/MovieSceneMaterialTrack.h"
#include "HAL/PlatformApplicationMisc.h"

#define LOCTEXT_NAMESPACE "MaterialDynamicParametersPanelWidget"

// Mineprep: Keyframe button styling constants
namespace KeyframeButtonConfig
{
	// Button size
	static const float ButtonSize = 16.0f;
	
	// Spacing between value widget and keyframe button
	static const float ValueToButtonSpacing = 1.0f;
	
	// Button padding
	static const FMargin ButtonPadding = FMargin(2.0f, 2.0f);
	
	// Value widget left padding
	static const FMargin ValueWidgetPadding = FMargin(5.0f, 2.0f, 2.0f, 2.0f);
}

enum class EMaterialParameterKeyKind : uint8
{
	Unsupported,
	Scalar,
	Vector,
	Texture,
	Font,
};

struct FResolvedMaterialParameterContext
{
	UMaterialInstance* MaterialInstance = nullptr;
	UMeshComponent* Component = nullptr;
	FComponentMaterialInfo MaterialInfo;
	FMaterialParameterInfo ParameterInfo;
	FString ParamType;
	FString ParamName;
	FString ParamValue;
	EMaterialParameterKeyKind KeyKind = EMaterialParameterKeyKind::Unsupported;
	float ScalarValue = 0.0f;
	FLinearColor VectorValue = FLinearColor::Transparent;
};

static const FName GMaterialKeyedStyleName("Sequencer.KeyedStatus.Keyed");
static const FName GMaterialUnkeyedStyleName("Sequencer.KeyedStatus.NotKeyed");
static const FName GMaterialLegacyStyleName("Sequencer.AddKey.Details");

static TSharedPtr<ISequencer> GetFocusedLevelSequencer()
{
	if (!GEditor)
	{
		return nullptr;
	}

	ULevelSequence* FocusedLevelSequence = ULevelSequenceEditorBlueprintLibrary::GetFocusedLevelSequence();
	if (!FocusedLevelSequence)
	{
		return nullptr;
	}

	UAssetEditorSubsystem* AssetEditorSubsystem = GEditor->GetEditorSubsystem<UAssetEditorSubsystem>();
	if (!AssetEditorSubsystem)
	{
		return nullptr;
	}

	IAssetEditorInstance* AssetEditor = AssetEditorSubsystem->FindEditorForAsset(FocusedLevelSequence, false);
	if (!AssetEditor)
	{
		return nullptr;
	}

	ILevelSequenceEditorToolkit* LevelSequenceEditor = static_cast<ILevelSequenceEditorToolkit*>(AssetEditor);
	return LevelSequenceEditor ? LevelSequenceEditor->GetSequencer() : nullptr;
}

static bool MaterialParameterInfoMatches(const FMaterialParameterInfo& A, const FMaterialParameterInfo& B)
{
	return A.Name == B.Name && A.Association == B.Association && A.Index == B.Index;
}

static bool ResolveMaterialOwnerComponent(UMaterialInstance* MaterialInstance, UMeshComponent*& OutComponent, FComponentMaterialInfo& OutMaterialInfo)
{
	if (!MaterialInstance)
	{
		return false;
	}

	auto TryResolveForComponent = [MaterialInstance, &OutComponent, &OutMaterialInfo](UMeshComponent* MeshComponent) -> bool
	{
		if (!IsValid(MeshComponent))
		{
			return false;
		}

		for (int32 MaterialIndex = 0; MaterialIndex < MeshComponent->GetNumMaterials(); ++MaterialIndex)
		{
			if (MeshComponent->GetMaterial(MaterialIndex) == MaterialInstance)
			{
				OutComponent = MeshComponent;
				OutMaterialInfo.MaterialSlotIndex = MaterialIndex;
				OutMaterialInfo.MaterialType = EComponentMaterialType::IndexedMaterial;
				OutMaterialInfo.MaterialSlotName = MeshComponent->GetMaterialSlotNames().IsValidIndex(MaterialIndex)
					? MeshComponent->GetMaterialSlotNames()[MaterialIndex]
					: NAME_None;
				return true;
			}
		}

		return false;
	};

	if (UMeshComponent* OuterMeshComponent = MaterialInstance->GetTypedOuter<UMeshComponent>())
	{
		if (TryResolveForComponent(OuterMeshComponent))
		{
			return true;
		}
	}

	for (TObjectIterator<UMeshComponent> It; It; ++It)
	{
		if (TryResolveForComponent(*It))
		{
			return true;
		}
	}

	return false;
}

static bool ResolveMaterialParameterContext(TWeakObjectPtr<UMaterialInstance> MaterialInstanceWeak, const FMaterialParameterInfo& ParameterInfo, FResolvedMaterialParameterContext& OutContext)
{
	if (!MaterialInstanceWeak.IsValid())
	{
		return false;
	}

	UMaterialInstance* MaterialInstance = MaterialInstanceWeak.Get();
	OutContext.MaterialInstance = MaterialInstance;
	OutContext.ParameterInfo = ParameterInfo;
	OutContext.ParamName = ParameterInfo.Name.ToString();
	ResolveMaterialOwnerComponent(MaterialInstance, OutContext.Component, OutContext.MaterialInfo);

	float ScalarValue = 0.0f;
	if (MaterialInstance->GetScalarParameterValue(ParameterInfo, ScalarValue))
	{
		OutContext.KeyKind = EMaterialParameterKeyKind::Scalar;
		OutContext.ParamType = TEXT("float");
		OutContext.ParamValue = FString::SanitizeFloat(ScalarValue);
		OutContext.ScalarValue = ScalarValue;
		return true;
	}

	FLinearColor VectorValue;
	if (MaterialInstance->GetVectorParameterValue(ParameterInfo, VectorValue))
	{
		OutContext.KeyKind = EMaterialParameterKeyKind::Vector;
		OutContext.ParamType = TEXT("FLinearColor");
		OutContext.ParamValue = VectorValue.ToString();
		OutContext.VectorValue = VectorValue;
		return true;
	}

	UTexture* TextureValue = nullptr;
	if (MaterialInstance->GetTextureParameterValue(ParameterInfo, TextureValue))
	{
		OutContext.KeyKind = EMaterialParameterKeyKind::Texture;
		OutContext.ParamType = TEXT("TObjectPtr<UTexture>");
		OutContext.ParamValue = TextureValue ? TextureValue->GetPathName() : TEXT("None");
		return true;
	}

	UFont* FontValue = nullptr;
	int32 FontPage = 0;
	if (MaterialInstance->GetFontParameterValue(ParameterInfo, FontValue, FontPage))
	{
		OutContext.KeyKind = EMaterialParameterKeyKind::Font;
		OutContext.ParamType = TEXT("TObjectPtr<UFont>");
		OutContext.ParamValue = FontValue ? FontValue->GetPathName() : TEXT("None");
		return true;
	}

	return false;
}

static bool IsNativeMaterialParameterKeyable(const FResolvedMaterialParameterContext& Context)
{
	return Context.Component != nullptr
		&& (Context.KeyKind == EMaterialParameterKeyKind::Scalar || Context.KeyKind == EMaterialParameterKeyKind::Vector);
}

static UMovieSceneComponentMaterialTrack* FindMaterialTrack(UMovieScene* MovieScene, const FGuid& ObjectBinding, const FComponentMaterialInfo& MaterialInfo)
{
	if (!MovieScene)
	{
		return nullptr;
	}

	const FMovieSceneBinding* Binding = MovieScene->FindBinding(ObjectBinding);
	if (!Binding)
	{
		return nullptr;
	}

	for (UMovieSceneTrack* Track : Binding->GetTracks())
	{
		UMovieSceneComponentMaterialTrack* MaterialTrack = Cast<UMovieSceneComponentMaterialTrack>(Track);
		if (MaterialTrack && MaterialTrack->GetMaterialInfo() == MaterialInfo)
		{
			return MaterialTrack;
		}
	}

	return nullptr;
}

static UMovieSceneSection* FindMaterialTrackSection(UMovieSceneComponentMaterialTrack* MaterialTrack)
{
	return MaterialTrack && MaterialTrack->GetAllSections().Num() > 0
		? MaterialTrack->GetAllSections()[0]
		: nullptr;
}

static bool FloatChannelHasAnyKeys(const FMovieSceneFloatChannel& Channel)
{
	return Channel.GetData().GetTimes().Num() > 0;
}

static bool HasAnyMaterialParameterKeys(UMovieSceneSection* Section, const FResolvedMaterialParameterContext& Context)
{
	if (!Section)
	{
		return false;
	}

	if (Context.KeyKind == EMaterialParameterKeyKind::Scalar)
	{
		if (const UMovieSceneComponentMaterialParameterSection* MaterialSection = Cast<UMovieSceneComponentMaterialParameterSection>(Section))
		{
			for (const FScalarMaterialParameterInfoAndCurve& ScalarParameter : MaterialSection->ScalarParameterInfosAndCurves)
			{
				if (MaterialParameterInfoMatches(ScalarParameter.ParameterInfo, Context.ParameterInfo) && FloatChannelHasAnyKeys(ScalarParameter.ParameterCurve))
				{
					return true;
				}
			}
		}

		if (const UMovieSceneParameterSection* LegacySection = Cast<UMovieSceneParameterSection>(Section))
		{
			for (const FScalarParameterNameAndCurve& ScalarParameter : LegacySection->GetScalarParameterNamesAndCurves())
			{
				if (ScalarParameter.ParameterName == Context.ParameterInfo.Name && FloatChannelHasAnyKeys(ScalarParameter.ParameterCurve))
				{
					return true;
				}
			}
		}
	}

	if (Context.KeyKind == EMaterialParameterKeyKind::Vector)
	{
		if (const UMovieSceneComponentMaterialParameterSection* MaterialSection = Cast<UMovieSceneComponentMaterialParameterSection>(Section))
		{
			for (const FColorMaterialParameterInfoAndCurves& ColorParameter : MaterialSection->ColorParameterInfosAndCurves)
			{
				if (MaterialParameterInfoMatches(ColorParameter.ParameterInfo, Context.ParameterInfo)
					&& (FloatChannelHasAnyKeys(ColorParameter.RedCurve)
						|| FloatChannelHasAnyKeys(ColorParameter.GreenCurve)
						|| FloatChannelHasAnyKeys(ColorParameter.BlueCurve)
						|| FloatChannelHasAnyKeys(ColorParameter.AlphaCurve)))
				{
					return true;
				}
			}
		}

		if (const UMovieSceneParameterSection* LegacySection = Cast<UMovieSceneParameterSection>(Section))
		{
			for (const FColorParameterNameAndCurves& ColorParameter : LegacySection->GetColorParameterNamesAndCurves())
			{
				if (ColorParameter.ParameterName == Context.ParameterInfo.Name
					&& (FloatChannelHasAnyKeys(ColorParameter.RedCurve)
						|| FloatChannelHasAnyKeys(ColorParameter.GreenCurve)
						|| FloatChannelHasAnyKeys(ColorParameter.BlueCurve)
						|| FloatChannelHasAnyKeys(ColorParameter.AlphaCurve)))
				{
					return true;
				}
			}
		}
	}

	return false;
}

static bool KeyFocusedMaterialParameter(const FResolvedMaterialParameterContext& Context, UMovieSceneComponentMaterialTrack** OutTrack = nullptr, UMovieSceneSection** OutSection = nullptr)
{
	if (OutTrack)
	{
		*OutTrack = nullptr;
	}

	if (OutSection)
	{
		*OutSection = nullptr;
	}

	if (!IsNativeMaterialParameterKeyable(Context))
	{
		return false;
	}

	TSharedPtr<ISequencer> Sequencer = GetFocusedLevelSequencer();
	if (!Sequencer.IsValid())
	{
		return false;
	}

	UMovieSceneSequence* FocusedSequence = Sequencer->GetFocusedMovieSceneSequence();
	UMovieScene* MovieScene = FocusedSequence ? FocusedSequence->GetMovieScene() : nullptr;
	if (!MovieScene || MovieScene->IsReadOnly())
	{
		return false;
	}

	const FScopedTransaction Transaction(LOCTEXT("InlineMaterialKeyParameter", "Key Material Parameter"));
	MovieScene->Modify();

	const FGuid ObjectBinding = Sequencer->GetHandleToObject(Context.Component, true);
	if (!ObjectBinding.IsValid())
	{
		return false;
	}

	bool bCreatedTrack = false;
	UMovieSceneComponentMaterialTrack* MaterialTrack = FindMaterialTrack(MovieScene, ObjectBinding, Context.MaterialInfo);
	if (!MaterialTrack)
	{
		MaterialTrack = NewObject<UMovieSceneComponentMaterialTrack>(MovieScene, NAME_None, RF_Transactional);
		MovieScene->AddGivenTrack(MaterialTrack, ObjectBinding);
		MaterialTrack->Modify();
		MaterialTrack->SetMaterialInfo(Context.MaterialInfo);
		MaterialTrack->SetDisplayName(FText::FromString(Context.MaterialInfo.ToString()));
		bCreatedTrack = true;
	}

	const int32 PreviousSectionCount = MaterialTrack->GetAllSections().Num();
	const FFrameNumber KeyTime = Sequencer->GetLocalTime().Time.FrameNumber;

	MaterialTrack->Modify();
	if (Context.KeyKind == EMaterialParameterKeyKind::Scalar)
	{
		MaterialTrack->AddScalarParameterKey(Context.ParameterInfo, KeyTime, Context.ScalarValue, FString(), FString());
	}
	else if (Context.KeyKind == EMaterialParameterKeyKind::Vector)
	{
		MaterialTrack->AddColorParameterKey(Context.ParameterInfo, KeyTime, Context.VectorValue, FString(), FString());
	}
	else
	{
		return false;
	}

	UMovieSceneSection* MaterialSection = FindMaterialTrackSection(MaterialTrack);
	const bool bCreatedSection = MaterialTrack->GetAllSections().Num() > PreviousSectionCount;
	Sequencer->NotifyMovieSceneDataChanged(
		(bCreatedTrack || bCreatedSection)
			? EMovieSceneDataChangeType::MovieSceneStructureItemAdded
			: EMovieSceneDataChangeType::TrackValueChanged);

	if (FSlateApplication::IsInitialized())
	{
		FSlateApplication::Get().InvalidateAllWidgets(false);
	}

	if (OutTrack)
	{
		*OutTrack = MaterialTrack;
	}

	if (OutSection)
	{
		*OutSection = MaterialSection;
	}

	return true;
}

static void NotifyMaterialKeyVariable(UObject* TargetObject, UObject* Object, UMovieSceneTrack* Track, UMovieSceneSection* Section, const FString& ParamType, const FString& ParamName, const FString& ParamValue)
{
	static const FString BlueprintPath = TEXT("/Mineprep/Mineprep自定义快捷键.Mineprep自定义快捷键_C");
	UClass* LoadedClass = LoadClass<UObject>(nullptr, *BlueprintPath);
	if (!LoadedClass)
	{
		return;
	}

	UObject* HotkeyObject = NewObject<UObject>(GetTransientPackage(), LoadedClass);
	if (!HotkeyObject)
	{
		return;
	}

	UFunction* KeyVarFunc = HotkeyObject->FindFunction(FName(TEXT("KeyVariable")));
	if (!KeyVarFunc)
	{
		return;
	}

	struct FKeyVariableParams
	{
		UObject* Target;
		UObject* Object;
		UMovieSceneTrack* Track;
		UMovieSceneSection* Section;
		FString ParamType;
		FString ParamName;
		FString ParamValue;
	} Params;

	Params.Target = TargetObject;
	Params.Object = Object;
	Params.Track = Track;
	Params.Section = Section;
	Params.ParamType = ParamType;
	Params.ParamName = ParamName;
	Params.ParamValue = ParamValue;

	HotkeyObject->ProcessEvent(KeyVarFunc, &Params);
}

static const FSlateBrush* GetMaterialKeyframeBrush(const FMaterialParameterInfo& ParameterInfo, TWeakObjectPtr<UMaterialInstance> MaterialInstanceWeak)
{
	FResolvedMaterialParameterContext Context;
	if (!ResolveMaterialParameterContext(MaterialInstanceWeak, ParameterInfo, Context))
	{
		return FAppStyle::Get().GetBrush(GMaterialLegacyStyleName);
	}

	if (!IsNativeMaterialParameterKeyable(Context))
	{
		return FAppStyle::Get().GetBrush(GMaterialLegacyStyleName);
	}

	TSharedPtr<ISequencer> Sequencer = GetFocusedLevelSequencer();
	if (!Sequencer.IsValid())
	{
		return FAppStyle::Get().GetBrush(GMaterialUnkeyedStyleName);
	}

	UMovieSceneSequence* FocusedSequence = Sequencer->GetFocusedMovieSceneSequence();
	UMovieScene* MovieScene = FocusedSequence ? FocusedSequence->GetMovieScene() : nullptr;
	if (!MovieScene)
	{
		return FAppStyle::Get().GetBrush(GMaterialUnkeyedStyleName);
	}

	const FGuid ObjectBinding = Sequencer->GetHandleToObject(Context.Component, false);
	if (!ObjectBinding.IsValid())
	{
		return FAppStyle::Get().GetBrush(GMaterialUnkeyedStyleName);
	}

	UMovieSceneComponentMaterialTrack* MaterialTrack = FindMaterialTrack(MovieScene, ObjectBinding, Context.MaterialInfo);
	UMovieSceneSection* MaterialSection = FindMaterialTrackSection(MaterialTrack);
	const FName& BrushName = HasAnyMaterialParameterKeys(MaterialSection, Context)
		? GMaterialKeyedStyleName
		: GMaterialUnkeyedStyleName;

	return FAppStyle::Get().GetBrush(BrushName);
}

static FReply HandleMaterialKeyframeButtonClick(const FMaterialParameterInfo ParameterInfo, TWeakObjectPtr<UMaterialInstance> MaterialInstanceWeak)
{
	FResolvedMaterialParameterContext Context;
	if (!ResolveMaterialParameterContext(MaterialInstanceWeak, ParameterInfo, Context))
	{
		UE_LOG(LogTemp, Warning, TEXT("无法解析材质参数关键帧上下文: %s"), *ParameterInfo.Name.ToString());
		return FReply::Handled();
	}

	UMovieSceneComponentMaterialTrack* MaterialTrack = nullptr;
	UMovieSceneSection* MaterialSection = nullptr;
	if (IsNativeMaterialParameterKeyable(Context)
		&& !KeyFocusedMaterialParameter(Context, &MaterialTrack, &MaterialSection))
	{
		UE_LOG(LogTemp, Warning, TEXT("为材质参数添加原生关键帧失败: %s"), *Context.ParamName);
	}

	NotifyMaterialKeyVariable(Context.MaterialInstance, Context.Component, MaterialTrack, MaterialSection, Context.ParamType, Context.ParamName, Context.ParamValue);
	return FReply::Handled();
}

enum EStackDataType
{
	Stack,
	Asset,
	Group,
	Property,
	PropertyChild,
};

struct FPropertySortedParamData
{
	EStackDataType StackDataType;

	FMaterialParameterInfo ParameterInfo;

	TSharedPtr<IDetailTreeNode> ParameterNode;

	TSharedPtr<IPropertyHandle> ParameterHandle;

	TArray<TSharedPtr<FPropertySortedParamData>> Children;

	FString NodeKey;

	FName GroupName;
};

struct FPropertyUnsortedParamData
{
	TSharedPtr<IDetailTreeNode> ParameterNode;

	TSharedPtr<IPropertyHandle> ParameterHandle;

	FMaterialParameterInfo ParameterInfo;

	FName GroupName;
};

namespace Utilities
{
	template<typename ParameterValueType>
	void AddParameters(TSharedPtr<IPropertyHandle> InPropertyHandle, const FName InParameterName, TArray<TSharedPtr<IPropertyHandle>>& OutDeferredSearches, TArray<FPropertyUnsortedParamData>& OutUnsortedParameters)
	{
		if (!InPropertyHandle.IsValid())
		{
			return;
		}
		
		TArray<void*> GroupPtrs;
		InPropertyHandle->AccessRawData(GroupPtrs);
		const auto GroupIt = GroupPtrs.CreateConstIterator();
		TArray<ParameterValueType>* ParameterGroupArrayPtr = reinterpret_cast<TArray<ParameterValueType>*>(*GroupIt);
		if (!ParameterGroupArrayPtr)
		{
			return;
		}

		const TSharedPtr<IPropertyHandleArray> ParameterValuesArray = InPropertyHandle->AsArray();

		uint32 NumElements = 0;
		ParameterValuesArray->GetNumElements(NumElements);
		for (uint32 Index = 0; Index < NumElements; ++Index)
		{
			const ParameterValueType& ParameterValue = (*ParameterGroupArrayPtr)[Index];
			if (!ParameterValue.ExpressionGUID.IsValid())
			{
				continue;
			}

			if (const TSharedPtr<IPropertyHandle> ElementPropertyHandle = ParameterValuesArray->GetElement(Index))
			{
				FPropertyUnsortedParamData NonLayerProperty;
				TSharedPtr<IPropertyHandle> ParameterValuePropertyHandle = ElementPropertyHandle->GetChildHandle(InParameterName);

				NonLayerProperty.ParameterInfo = ParameterValue.ParameterInfo;
				NonLayerProperty.GroupName = TEXT("Group");

				OutDeferredSearches.Add(ParameterValuePropertyHandle);
				OutUnsortedParameters.Add(NonLayerProperty);
			}
		}
	}
};

// ********* SMaterialParametersOverviewTree *******
class SMaterialDynamicParametersOverviewTree : public STreeView<TSharedPtr<FPropertySortedParamData>>
{
	friend class SMaterialDynamicParametersOverviewTreeItem;

public:

	SLATE_BEGIN_ARGS(SMaterialDynamicParametersOverviewTree)
	{}

	SLATE_ARGUMENT(UMaterialInstance*, InMaterialInstance)
	SLATE_ARGUMENT(TSharedPtr<SMaterialDynamicParametersPanelWidget>, InOwner)
	SLATE_ARGUMENT(TSharedPtr<SScrollBar>, InScrollbar)
	SLATE_END_ARGS()

	/** Constructs this widget with InArgs */
	void Construct(const FArguments& InArgs);
	TSharedRef< ITableRow > OnGenerateRowMaterialLayersFunctionsTreeView(TSharedPtr<FPropertySortedParamData> Item, const TSharedRef< STableViewBase >& OwnerTable);
	void OnGetChildrenMaterialLayersFunctionsTreeView(TSharedPtr<FPropertySortedParamData> InParent, TArray< TSharedPtr<FPropertySortedParamData> >& OutChildren);
	void OnExpansionChanged(TSharedPtr<FPropertySortedParamData> Item, bool bIsExpanded);
	void SetParentsExpansionState();

	/** Builds the custom parameter groups category */
	void CreateGroupsWidget();

	TWeakPtr<SMaterialDynamicParametersPanelWidget> GetOwner() { return Owner; }
	bool HasAnyParameters() const { return bHasAnyParameters; }

	FDetailColumnSizeData& GetColumnSizeData() { return ColumnSizeData; }

protected:

	void ShowSubParameters();

public:
	/** Object that stores all of the possible parameters we can edit */
	TWeakObjectPtr<UMaterialInstance> MaterialInstance;

private:
	TArray<TSharedPtr<FPropertySortedParamData>> SortedParameters;

	TArray<FPropertyUnsortedParamData> UnsortedParameters;

	TWeakPtr<SMaterialDynamicParametersPanelWidget> Owner;

	bool bHasAnyParameters;
	
	FDetailColumnSizeData ColumnSizeData;
};

// ********* SMaterialParametersOverviewTreeItem *******
class SMaterialDynamicParametersOverviewTreeItem : public STableRow< TSharedPtr<FPropertySortedParamData> >
{
public:

	SLATE_BEGIN_ARGS(SMaterialDynamicParametersOverviewTreeItem)
		: _StackParameterData(nullptr),
		_MaterialInstance(nullptr)
	{}

	/** The item content. */
	SLATE_ARGUMENT(TSharedPtr<FPropertySortedParamData>, StackParameterData)
	SLATE_ARGUMENT(UMaterialInstance*, MaterialInstance)
	SLATE_ARGUMENT(TSharedPtr<SMaterialDynamicParametersOverviewTree>, InTree)
	SLATE_END_ARGS()

	void RefreshOnRowChange(const FAssetData& AssetData, TSharedPtr<SMaterialDynamicParametersOverviewTree> InTree);

	/**
	* Construct the widget
	*
	* @param InArgs   A declaration from which to construct the widget
	*/
	void Construct(const FArguments& InArgs, const TSharedRef<STableViewBase>& InOwnerTableView);

public:
	// 重写鼠标事件以支持快捷键和右键菜单
	virtual FReply OnMouseButtonUp(const FGeometry& MyGeometry, const FPointerEvent& MouseEvent) override;

private:
	const FSlateBrush* GetBorderImage() const;

	FSlateColor GetOuterBackgroundColor(TSharedPtr<FPropertySortedParamData> InParamData) const;

	TSharedRef<SWidget> GetRowExtensionButtons(TSharedPtr<IPropertyHandle> InPropertyHandle);

	// 生成右键菜单
	TSharedPtr<SWidget> OnGenerateContextMenu();
private:

	/** The node info to build the tree view row from. */
	TSharedPtr<FPropertySortedParamData> StackParameterData;

	/** The tree that contains this item */
	TWeakPtr<SMaterialDynamicParametersOverviewTree> Tree;

	/** The set of material parameters this is associated with */
	TWeakObjectPtr<UMaterialInstance> MaterialInstance;

	/** Pointer to copied ValuePtr. Needed for workaround for now */
	TUniquePtr<uint8> NewDefaultValuePtr;

	/** Pointer to Widget for Workaround. */
	TSharedPtr<SWidget> ResetArrow;
};



FReply SMaterialDynamicParametersOverviewTreeItem::OnMouseButtonUp(const FGeometry& MyGeometry, const FPointerEvent& MouseEvent)
{
	// 只对Property类型的行处理
	if (StackParameterData.IsValid() && StackParameterData->StackDataType == EStackDataType::Property)
	{
		TSharedPtr<IPropertyHandle> Handle = StackParameterData->ParameterNode.IsValid() ? 
			StackParameterData->ParameterNode->CreatePropertyHandle() : nullptr;

		if (MouseEvent.GetModifierKeys().IsShiftDown() && Handle.IsValid())
		{
			// SHIFT + 右键 -> 复制
			if (MouseEvent.GetEffectingButton() == EKeys::RightMouseButton)
			{
				FString Value;
				if (Handle->GetValueAsFormattedString(Value, PPF_Copy) == FPropertyAccess::Success)
				{
					FPlatformApplicationMisc::ClipboardCopy(*Value);
					return FReply::Handled();
				}
			}
			// SHIFT + 左键 -> 粘贴
			else if (MouseEvent.GetEffectingButton() == EKeys::LeftMouseButton)
			{
				FString ClipboardContent;
				FPlatformApplicationMisc::ClipboardPaste(ClipboardContent);
				if (!ClipboardContent.IsEmpty())
				{
					Handle->SetValueFromFormattedString(ClipboardContent);
				}
				return FReply::Handled();
			}
		}

		// 普通右键点击 -> 弹出上下文菜单
		if (MouseEvent.GetEffectingButton() == EKeys::RightMouseButton && !MouseEvent.GetModifierKeys().IsShiftDown())
		{
			TSharedPtr<SWidget> MenuWidget = OnGenerateContextMenu();
			if (MenuWidget.IsValid())
			{
				FWidgetPath WidgetPath = MouseEvent.GetEventPath() != nullptr ? *MouseEvent.GetEventPath() : FWidgetPath();
				FSlateApplication::Get().PushMenu(
					SharedThis(this),
					WidgetPath,
					MenuWidget.ToSharedRef(),
					MouseEvent.GetScreenSpacePosition(),
					FPopupTransitionEffect::ContextMenu
				);
				return FReply::Handled();
			}
		}
	}

	return STableRow::OnMouseButtonUp(MyGeometry, MouseEvent);
}

TSharedPtr<SWidget> SMaterialDynamicParametersOverviewTreeItem::OnGenerateContextMenu()
{
	if (!StackParameterData.IsValid() || StackParameterData->StackDataType != EStackDataType::Property)
	{
		return nullptr;
	}

	TSharedPtr<IPropertyHandle> Handle = StackParameterData->ParameterNode.IsValid() ? 
		StackParameterData->ParameterNode->CreatePropertyHandle() : nullptr;

	FMenuBuilder MenuBuilder(true, nullptr);

	// 获取显示名称
	FString DisplayName = StackParameterData->ParameterInfo.Name.ToString();
	FText LocalizedName;
	if (FText::FindTextInLiveTable_Advanced(FTextKey(TEXT("UObjectDisplayNames")), FTextKey(*DisplayName), LocalizedName, &DisplayName))
	{
		DisplayName = LocalizedName.ToString();
	}

	// 获取内部名称
	FString InternalName = StackParameterData->ParameterInfo.Name.ToString();

	if (Handle.IsValid())
	{
		// 复制值
		MenuBuilder.AddMenuEntry(
			NSLOCTEXT("PropertyView", "CopyProperty", "Copy"),
			NSLOCTEXT("PropertyView", "CopyProperty_ToolTip", "Copy this property value"),
			FSlateIcon(FAppStyle::GetAppStyleSetName(), "GenericCommands.Copy"),
			FUIAction(FExecuteAction::CreateLambda([Handle]() {
				FString Value;
				if (Handle->GetValueAsFormattedString(Value, PPF_Copy) == FPropertyAccess::Success)
				{
					FPlatformApplicationMisc::ClipboardCopy(*Value);
				}
			}))
		);

		// 粘贴值
		MenuBuilder.AddMenuEntry(
			NSLOCTEXT("PropertyView", "PasteProperty", "Paste"),
			NSLOCTEXT("PropertyView", "PasteProperty_ToolTip", "Paste the copied value here"),
			FSlateIcon(FAppStyle::GetAppStyleSetName(), "GenericCommands.Paste"),
			FUIAction(FExecuteAction::CreateLambda([Handle]() {
				FString ClipboardContent;
				FPlatformApplicationMisc::ClipboardPaste(ClipboardContent);
				if (!ClipboardContent.IsEmpty())
				{
					Handle->SetValueFromFormattedString(ClipboardContent);
				}
			}))
		);

		MenuBuilder.AddSeparator();
	}

	// 复制显示名称
	MenuBuilder.AddMenuEntry(
		NSLOCTEXT("PropertyView", "CopyPropertyDisplayName", "Copy Display Name"),
		FText::Format(NSLOCTEXT("PropertyView_Single", "CopyPropertyDisplayName_ToolTip", "Copy the display name of this property to the system clipboard:\n{0}"), FText::FromString(DisplayName)),
		FSlateIcon(FAppStyle::GetAppStyleSetName(), "GenericCommands.Copy"),
		FUIAction(FExecuteAction::CreateLambda([DisplayName]() {
			FPlatformApplicationMisc::ClipboardCopy(*DisplayName);
		}))
	);

	// 复制内部名称
	MenuBuilder.AddMenuEntry(
		NSLOCTEXT("PropertyView", "CopyPropertyInternalName", "Copy Internal Name"),
		FText::Format(NSLOCTEXT("PropertyView_Single", "CopyPropertyInternalName_ToolTip", "Copy the internal name of this property to the system clipboard:\n{0}"), FText::FromString(InternalName)),
		FSlateIcon(FAppStyle::GetAppStyleSetName(), "GenericCommands.Copy"),
		FUIAction(FExecuteAction::CreateLambda([InternalName]() {
			FPlatformApplicationMisc::ClipboardCopy(*InternalName);
		}))
	);

	return MenuBuilder.MakeWidget();
}

const FSlateBrush* SMaterialDynamicParametersOverviewTreeItem::GetBorderImage() const
{
	return FAppStyle::Get().GetBrush("DetailsView.CategoryMiddle");
}

FSlateColor SMaterialDynamicParametersOverviewTreeItem::GetOuterBackgroundColor(TSharedPtr<FPropertySortedParamData> InParamData) const
{
	if (IsHovered() || InParamData->StackDataType == EStackDataType::Group)
	{
		return FAppStyle::Get().GetSlateColor("Colors.Header");
	}

	return FAppStyle::Get().GetSlateColor("Colors.Panel");
}

TSharedRef<SWidget> SMaterialDynamicParametersOverviewTreeItem::GetRowExtensionButtons(TSharedPtr<IPropertyHandle> InPropertyHandle)
{
	if (!InPropertyHandle.IsValid())
	{
		return SNullWidget::NullWidget;
	}

	const auto ResetDelegate = FExecuteAction::CreateLambda([this, InPropertyHandle]()
	{
		if (InPropertyHandle.IsValid())
		{
			InPropertyHandle->ResetToDefault();
			ResetArrow->SetVisibility(EVisibility::Hidden);
		}
	});

	/** Needed as Dynamic Material Instances don't have a default to use normally for DiffersFromDefault */
	const auto DiffersFromDefaultDelegate = FIsActionButtonVisible::CreateLambda([this, InPropertyHandle]()
	{
		if (!NewDefaultValuePtr)
		{
			return true;
		}

		FProperty* Property = InPropertyHandle->GetProperty();
		
		void* ValuePtr;
		InPropertyHandle->GetValueData(ValuePtr);
		
		if (Property->Identical(NewDefaultValuePtr.Get(), ValuePtr))
		{
			return false;
		}
		return true;
	});
	
	FPropertyEditorModule& PropertyEditorModule = FModuleManager::Get().GetModuleChecked<FPropertyEditorModule>("PropertyEditor");

	TArray<FPropertyRowExtensionButton> ExtensionButtons;
	FPropertyRowExtensionButton& ResetToDefault = ExtensionButtons.AddDefaulted_GetRef();
	ResetToDefault.Label = NSLOCTEXT("PropertyEditor", "ResetToDefault", "Reset to Default");
	ResetToDefault.UIAction = FUIAction(ResetDelegate, FCanExecuteAction(), FIsActionChecked(), DiffersFromDefaultDelegate);

	ResetToDefault.Icon = FSlateIcon(FAppStyle::Get().GetStyleSetName(), "PropertyWindow.DiffersFromDefault");
	ResetToDefault.ToolTip = NSLOCTEXT("PropertyEditor", "ResetToDefaultToolTip", "Reset this property to its default value.");

	// Mineprep: Keyframe button temporarily commented out to test stability
	/*
	// Add keyframe button
	FPropertyRowExtensionButton& KeyframeButton = ExtensionButtons.AddDefaulted_GetRef();
	KeyframeButton.Label = NSLOCTEXT("MaterialEditor", "AddKeyframe", "Add Keyframe");
	KeyframeButton.ToolTip = NSLOCTEXT("MaterialEditor", "AddKeyframeToolTip", "Add a keyframe for this material parameter.");
	KeyframeButton.Icon = FSlateIcon(FAppStyle::GetAppStyleSetName(), "Sequencer.AddKey.Details");
	
	// Keyframe button click action (placeholder - no action for now)
	auto KeyframeDelegate = FExecuteAction::CreateLambda([InPropertyHandle]()
	{
		// TODO: Add keyframe logic here
		UE_LOG(LogTemp, Log, TEXT("Keyframe button clicked for parameter: %s"), 
			InPropertyHandle.IsValid() ? *InPropertyHandle->GetPropertyDisplayName().ToString() : TEXT("Invalid"));
	});
	
	KeyframeButton.UIAction = FUIAction(KeyframeDelegate);
	*/

	// Add custom property extensions
	FOnGenerateGlobalRowExtensionArgs RowExtensionArgs;
	RowExtensionArgs.PropertyHandle = InPropertyHandle;
	PropertyEditorModule.GetGlobalRowExtensionDelegate().Broadcast(RowExtensionArgs, ExtensionButtons);
	
	// Build extension toolbar 
	FSlimHorizontalToolBarBuilder ToolbarBuilder(TSharedPtr<FUICommandList>(), FMultiBoxCustomization::None);
	ToolbarBuilder.SetLabelVisibility(EVisibility::Collapsed);
	ToolbarBuilder.SetStyle(&FAppStyle::Get(), "DetailsView.ExtensionToolBar");
	for (const FPropertyRowExtensionButton& Extension : ExtensionButtons)
	{
		ToolbarBuilder.AddToolBarButton(Extension.UIAction, NAME_None, Extension.Label, Extension.ToolTip, Extension.Icon);
	}

	/** Set up the Default Value for the Workaround. */
	FProperty* Property = InPropertyHandle->GetProperty();
	NewDefaultValuePtr = MakeUnique<uint8>(Property->GetSize());
	void* ValuePtr;
	InPropertyHandle->GetValueData(ValuePtr);
	Property->CopyCompleteValue(NewDefaultValuePtr.Get(), ValuePtr);
	Property->ClearValue(NewDefaultValuePtr.Get());
	
	ResetArrow = ToolbarBuilder.MakeWidget();
	
	return ResetArrow.ToSharedRef();
}

void SMaterialDynamicParametersOverviewTreeItem::RefreshOnRowChange(const FAssetData& AssetData, TSharedPtr<SMaterialDynamicParametersOverviewTree> InTree)
{
	if (InTree.IsValid())
	{
		InTree->CreateGroupsWidget();
	}
}

void SMaterialDynamicParametersOverviewTreeItem::Construct(const FArguments& InArgs, const TSharedRef<STableViewBase>& InOwnerTableView)
{
	StackParameterData = InArgs._StackParameterData;
	MaterialInstance = InArgs._MaterialInstance;
	Tree = InArgs._InTree;

	TSharedRef<SWidget> LeftSideWidget = SNullWidget::NullWidget;
	TSharedRef<SWidget> RightSideWidget = SNullWidget::NullWidget;
	FText NameOverride;
	TSharedRef<SVerticalBox> WrapperWidget = SNew(SVerticalBox);

	auto GenerateLeftAndRightWidgets = [&](IDetailTreeNode& InNode)
	{
		const FNodeWidgets NodeWidgets = InNode.CreateNodeWidgets();
		if (NodeWidgets.NameWidget.IsValid() && NodeWidgets.ValueWidget.IsValid())
		{
			LeftSideWidget = NodeWidgets.NameWidget.ToSharedRef();
			RightSideWidget = SNew(SHorizontalBox)
					+SHorizontalBox::Slot()
					.FillWidth(1.f)
					[
						NodeWidgets.ValueWidget.ToSharedRef()
					];
		}
	};

// GROUP --------------------------------------------------
	if (StackParameterData->StackDataType == EStackDataType::Group)
	{
		NameOverride = FText::FromName(StackParameterData->GroupName);
		LeftSideWidget = SNew(STextBlock)
			.TransformPolicy(ETextTransformPolicy::ToUpper)
			.Text(NameOverride)
			.Font(FAppStyle::Get().GetFontStyle("PropertyWindow.BoldFont"))
			.TextStyle(FAppStyle::Get(), "DetailsView.CategoryTextStyle");
	}
// END GROUP

// PROPERTY ----------------------------------------------
	bool bIsPaddedProperty = false;
	if (StackParameterData->StackDataType == EStackDataType::Property)
	{
		// Mineprep: 尝试从本地化表中查找文本，如果找不到则使用原始名称
		FString ParamNameStr = StackParameterData->ParameterInfo.Name.ToString();
		if (!FText::FindTextInLiveTable_Advanced(FTextKey(TEXT("UObjectDisplayNames")), FTextKey(*ParamNameStr), NameOverride, &ParamNameStr))
		{
			NameOverride = FText::FromName(StackParameterData->ParameterInfo.Name);
		}

		IDetailTreeNode& Node = *StackParameterData->ParameterNode;
		TSharedPtr<IDetailPropertyRow> GeneratedRow = StaticCastSharedPtr<IDetailPropertyRow>(Node.GetRow());
		IDetailPropertyRow& Row = *GeneratedRow.Get();
		Row.DisplayName(NameOverride);


		if (TSharedPtr<IPropertyHandle> PropertyHandle = StackParameterData->ParameterNode->CreatePropertyHandle())
		{
			PropertyHandle->MarkResetToDefaultCustomized(true);
		}

		// 构建tooltip文本：显示名称 + 内部名称
		FText TooltipText = FText::Format(
			LOCTEXT("ParameterTooltipFormat", "{0}\n(Internal: {1})"),
			NameOverride,
			FText::FromName(StackParameterData->ParameterInfo.Name)
		);

		// 创建带tooltip的名称widget
		LeftSideWidget = SNew(STextBlock)
			.Text(NameOverride)
			.ToolTipText(TooltipText)
			.Font(FAppStyle::GetFontStyle(TEXT("PropertyWindow.NormalFont")));

		// 只获取ValueWidget，不覆盖LeftSideWidget
		const FNodeWidgets NodeWidgets = Node.CreateNodeWidgets();
		if (NodeWidgets.ValueWidget.IsValid())
		{
			RightSideWidget = SNew(SHorizontalBox)
				+SHorizontalBox::Slot()
				.FillWidth(1.f)
				[
					NodeWidgets.ValueWidget.ToSharedRef()
				];
		}

		bIsPaddedProperty = true;
	}
// END PROPERTY

// PROPERTY CHILD ----------------------------------------
	if (StackParameterData->StackDataType == EStackDataType::PropertyChild)
	{
		GenerateLeftAndRightWidgets(*StackParameterData->ParameterNode);
	}
// END PROPERTY CHILD

// FINAL WRAPPER

	{
		FDetailColumnSizeData& ColumnSizeData = InArgs._InTree->GetColumnSizeData();

		float ValuePadding = bIsPaddedProperty ? 20.0f : 0.0f;
		WrapperWidget->AddSlot()
			.AutoHeight()
			[
				SNew(SBorder)
				.BorderImage(FAppStyle::Get().GetBrush("DetailsView.GridLine"))
				.Padding(FMargin(0, 0, 0, 1))
				[
					SNew(SBorder)
					.Padding(3.0f)
					.BorderImage(this, &SMaterialDynamicParametersOverviewTreeItem::GetBorderImage)
					.BorderBackgroundColor(this, &SMaterialDynamicParametersOverviewTreeItem::GetOuterBackgroundColor, StackParameterData)
					[
						SNew(SSplitter)
						.Style(FAppStyle::Get(), "DetailsView.Splitter")
						.PhysicalSplitterHandleSize(1.0f)
						.HitDetectionSplitterHandleSize(5.0f)
						+ SSplitter::Slot()
						.Value(ColumnSizeData.GetNameColumnWidth())
						.OnSlotResized(ColumnSizeData.GetOnNameColumnResized())
						.Value(0.25f)
						[
							SNew(SHorizontalBox)
							+ SHorizontalBox::Slot()
							.AutoWidth()
							.VAlign(VAlign_Center)
							.Padding(FMargin(3.0f))
							[
								SNew(SExpanderArrow, SharedThis(this))
							]
							+ SHorizontalBox::Slot()
							.Padding(FMargin(2.0f))
							.VAlign(VAlign_Center)
							[
								LeftSideWidget
							]
						]
						+ SSplitter::Slot()
						.Value(ColumnSizeData.GetValueColumnWidth())
						.OnSlotResized(ColumnSizeData.GetOnValueColumnResized()) 
						[
							SNew(SHorizontalBox)
							+ SHorizontalBox::Slot()
							.Padding(KeyframeButtonConfig::ValueWidgetPadding)
							.HAlign(HAlign_Fill)
							.VAlign(VAlign_Center)
							.FillWidth(1.0f)
							[
								RightSideWidget
							]
							// Mineprep: Add keyframe button for Property type only
							+ SHorizontalBox::Slot()
							.AutoWidth()
							.HAlign(HAlign_Right)
							.VAlign(VAlign_Center)
							.Padding(FMargin(KeyframeButtonConfig::ValueToButtonSpacing, 0.0f, 2.0f, 0.0f))
							[
								(StackParameterData->StackDataType == EStackDataType::Property) 
								? SNew(SButton)
									.ButtonStyle(FAppStyle::Get(), "SimpleButton")
									.ContentPadding(KeyframeButtonConfig::ButtonPadding)
									.ToolTipText(LOCTEXT("AddKeyframeTooltip", "Add a keyframe for this material parameter"))
									.OnClicked_Static(&HandleMaterialKeyframeButtonClick, StackParameterData->ParameterInfo, TWeakObjectPtr<UMaterialInstance>(MaterialInstance.Get()))
									[
										SNew(SBox)
										.WidthOverride(KeyframeButtonConfig::ButtonSize)
										.HeightOverride(KeyframeButtonConfig::ButtonSize)
										[
											SNew(SImage)
											.Image_Lambda([ParameterInfo = StackParameterData->ParameterInfo, MaterialInstanceWeak = TWeakObjectPtr<UMaterialInstance>(MaterialInstance.Get())]()
											{
												return GetMaterialKeyframeBrush(ParameterInfo, MaterialInstanceWeak);
											})
											.ColorAndOpacity(FSlateColor::UseForeground())
										]
									]
								: SNullWidget::NullWidget
							]
						]
					]
				]
			];
	}

	ChildSlot
		[
			WrapperWidget
		];


	STableRow< TSharedPtr<FPropertySortedParamData> >::ConstructInternal(
		STableRow::FArguments()
		.Style(FAppStyle::Get(), "DetailsView.TreeView.TableRow")
		.ShowSelection(false),
		InOwnerTableView
	);
}

void SMaterialDynamicParametersOverviewTree::Construct(const FArguments& InArgs)
{
	bHasAnyParameters = false;
	MaterialInstance = InArgs._InMaterialInstance;
	Owner = InArgs._InOwner;
	CreateGroupsWidget();

	STreeView<TSharedPtr<FPropertySortedParamData>>::Construct(
		STreeView::FArguments()
		.TreeItemsSource(&SortedParameters)
		.SelectionMode(ESelectionMode::None)
		.OnGenerateRow(this, &SMaterialDynamicParametersOverviewTree::OnGenerateRowMaterialLayersFunctionsTreeView)
		.OnGetChildren(this, &SMaterialDynamicParametersOverviewTree::OnGetChildrenMaterialLayersFunctionsTreeView)
		.OnExpansionChanged(this, &SMaterialDynamicParametersOverviewTree::OnExpansionChanged)
		.ExternalScrollbar(InArgs._InScrollbar)
	);
}

TSharedRef< ITableRow > SMaterialDynamicParametersOverviewTree::OnGenerateRowMaterialLayersFunctionsTreeView(TSharedPtr<FPropertySortedParamData> Item, const TSharedRef< STableViewBase >& OwnerTable)
{
	TSharedRef< SMaterialDynamicParametersOverviewTreeItem > ReturnRow = SNew(SMaterialDynamicParametersOverviewTreeItem, OwnerTable)
		.StackParameterData(Item)
		.MaterialInstance(MaterialInstance.Get())
		.InTree(SharedThis(this));
	return ReturnRow;
}

void SMaterialDynamicParametersOverviewTree::OnGetChildrenMaterialLayersFunctionsTreeView(TSharedPtr<FPropertySortedParamData> InParent, TArray< TSharedPtr<FPropertySortedParamData> >& OutChildren)
{
	OutChildren = InParent->Children;
}

void SMaterialDynamicParametersOverviewTree::OnExpansionChanged(TSharedPtr<FPropertySortedParamData> Item, bool bIsExpanded)
{
	bool* ExpansionValue = MaterialInstance->ParameterOverviewExpansion.Find(Item->NodeKey);
	if (ExpansionValue == nullptr)
	{
		MaterialInstance->ParameterOverviewExpansion.Add(Item->NodeKey, bIsExpanded);
	}
	else if (*ExpansionValue != bIsExpanded)
	{
		MaterialInstance->ParameterOverviewExpansion.Emplace(Item->NodeKey, bIsExpanded);
	}
	// Expand any children that are also expanded
	for (TSharedPtr<FPropertySortedParamData> Child : Item->Children)
	{
		bool* ChildExpansionValue = MaterialInstance->ParameterOverviewExpansion.Find(Child->NodeKey);
		if (ChildExpansionValue != nullptr && *ChildExpansionValue == true)
		{
			SetItemExpansion(Child, true);
		}
	}
}

void SMaterialDynamicParametersOverviewTree::SetParentsExpansionState()
{
	for (const auto& Pair : SortedParameters)
	{
		if (Pair->Children.Num())
		{
			bool* bIsExpanded = MaterialInstance->ParameterOverviewExpansion.Find(Pair->NodeKey);
			if (bIsExpanded)
			{
				SetItemExpansion(Pair, *bIsExpanded);
			}
			else
			{
				SetItemExpansion(Pair, true);
			}
		}
	}
}

void SMaterialDynamicParametersOverviewTree::CreateGroupsWidget()
{
	check(MaterialInstance.IsValid());
	UnsortedParameters.Reset();
	SortedParameters.Reset();

	const TArray<TSharedRef<IDetailTreeNode>> TestData = GetOwner().Pin()->Generator->GetRootTreeNodes();
	if (TestData.Num() == 0)
	{
		return;
	}
	TSharedPtr<IDetailTreeNode> Category = TestData[0];
	TSharedPtr<IDetailTreeNode> ParameterGroups;
	TArray<TSharedRef<IDetailTreeNode>> Children;
	Category->GetChildren(Children);

	TArray<TSharedPtr<IPropertyHandle>> DeferredSearches;

	for (int32 ChildIdx = 0; ChildIdx < Children.Num(); ChildIdx++)
	{
		TSharedPtr<IPropertyHandle> PropertyHandle = Children[ChildIdx]->CreatePropertyHandle();

		bHasAnyParameters = true;

		if (!PropertyHandle.IsValid() || !PropertyHandle->GetProperty())
		{
			continue;
		}

		if (PropertyHandle->GetProperty()->GetFName() == GET_MEMBER_NAME_CHECKED(UMaterialInstance, ScalarParameterValues))
		{
			Utilities::AddParameters<FScalarParameterValue>(PropertyHandle,
			                                                 GET_MEMBER_NAME_CHECKED(
				                                                 FScalarParameterValue, ParameterValue),
			                                                 DeferredSearches, UnsortedParameters);
		}
		else if (PropertyHandle->GetProperty()->GetFName() == GET_MEMBER_NAME_CHECKED(UMaterialInstance, VectorParameterValues))
		{
			Utilities::AddParameters<FVectorParameterValue>(PropertyHandle,
															GET_MEMBER_NAME_CHECKED(
																FVectorParameterValue, ParameterValue),
															DeferredSearches, UnsortedParameters);
		}
		else if (PropertyHandle->GetProperty()->GetFName() == GET_MEMBER_NAME_CHECKED(UMaterialInstance, TextureParameterValues))
		{
			Utilities::AddParameters<FTextureParameterValue>(PropertyHandle,
															GET_MEMBER_NAME_CHECKED(
																FTextureParameterValue, ParameterValue),
															DeferredSearches, UnsortedParameters);
		}
		else if (PropertyHandle->GetProperty()->GetFName() == GET_MEMBER_NAME_CHECKED(UMaterialInstance, FontParameterValues))
		{
			Utilities::AddParameters<FFontParameterValue>(PropertyHandle,
															GET_MEMBER_NAME_CHECKED(
																FFontParameterValue, FontValue),
															DeferredSearches, UnsortedParameters);
		}
	}

	checkf(UnsortedParameters.Num() == DeferredSearches.Num(), TEXT("Internal inconsistency: number of node searches does not match the number of properties"));
	TArray<TSharedPtr<IDetailTreeNode>> DeferredResults = GetOwner().Pin()->Generator->FindTreeNodes(DeferredSearches);
	checkf(UnsortedParameters.Num() == DeferredResults.Num(), TEXT("Internal inconsistency: number of node search results does not match the number of properties"));

	for (int Idx = 0, NumUnsorted = UnsortedParameters.Num(); Idx < NumUnsorted; ++Idx)
	{
		FPropertyUnsortedParamData& NonLayerProperty = UnsortedParameters[Idx];
		NonLayerProperty.ParameterNode = DeferredResults[Idx];
		NonLayerProperty.ParameterHandle = NonLayerProperty.ParameterNode->CreatePropertyHandle();
	}

	Children.Empty();

	ShowSubParameters();
	RequestTreeRefresh();
	SetParentsExpansionState();
}

void SMaterialDynamicParametersOverviewTree::ShowSubParameters()
{
	for (FPropertyUnsortedParamData Property : UnsortedParameters)
	{
		TSharedPtr<FPropertySortedParamData> GroupProperty(new FPropertySortedParamData());
		GroupProperty->ParameterInfo = Property.ParameterInfo;
		GroupProperty->StackDataType = EStackDataType::Group;
		GroupProperty->GroupName = Property.GroupName;
		GroupProperty->NodeKey = FString::FromInt(GroupProperty->ParameterInfo.Index) + FString::FromInt(GroupProperty->ParameterInfo.Association) + Property.GroupName.ToString();

		bool bAddNewGroup = true;
		for (TSharedPtr<struct FPropertySortedParamData> GroupChild : SortedParameters)
		{
			if (GroupChild->NodeKey == GroupProperty->NodeKey)
			{
				bAddNewGroup = false;
			}
		}
		if (bAddNewGroup)
		{
			SortedParameters.Add(GroupProperty);
		}

		TSharedPtr<FPropertySortedParamData> ChildProperty(new FPropertySortedParamData());
		ChildProperty->ParameterInfo = Property.ParameterInfo;
		ChildProperty->StackDataType = EStackDataType::Property;
		ChildProperty->ParameterNode = Property.ParameterNode;
		ChildProperty->NodeKey = FString::FromInt(ChildProperty->ParameterInfo.Index) + FString::FromInt(ChildProperty->ParameterInfo.Association) + Property.GroupName.ToString() + Property.ParameterInfo.Name.ToString();

		TArray<TSharedRef<IDetailTreeNode>> ParamChildren;
		Property.ParameterNode->GetChildren(ParamChildren);
		for (int32 ParamChildIdx = 0; ParamChildIdx < ParamChildren.Num(); ParamChildIdx++)
		{
			TSharedPtr<FPropertySortedParamData> ParamChildProperty(new FPropertySortedParamData());
			ParamChildProperty->StackDataType = EStackDataType::PropertyChild;
			ParamChildProperty->ParameterNode = ParamChildren[ParamChildIdx];
			ParamChildProperty->ParameterHandle = ParamChildProperty->ParameterNode->CreatePropertyHandle();
			ParamChildProperty->ParameterInfo = Property.ParameterInfo;
			ChildProperty->Children.Add(ParamChildProperty);
		}

		for (TSharedPtr<struct FPropertySortedParamData> GroupChild : SortedParameters)
		{
			if (GroupChild->GroupName == Property.GroupName
				&& GroupChild->ParameterInfo.Association == ChildProperty->ParameterInfo.Association
				&&  GroupChild->ParameterInfo.Index == ChildProperty->ParameterInfo.Index)
			{
				GroupChild->Children.Add(ChildProperty);
			}
		}
	}
}

void SMaterialDynamicParametersPanelWidget::Refresh()
{
	TSharedPtr<SHorizontalBox> HeaderBox;
	NestedTree->CreateGroupsWidget();

	if (NestedTree->HasAnyParameters())
	{
		this->ChildSlot
		[
			SNew(SVerticalBox)
			+ SVerticalBox::Slot()
			.Padding(0.0f)
			[
				
				SNew(SVerticalBox)
				+ SVerticalBox::Slot()
				.AutoHeight()
				[
					SAssignNew(HeaderBox, SHorizontalBox)
				]
				+ SVerticalBox::Slot()
				.Padding(0.0f)
				.MaxHeight(300.f)
				[
					SNew(SHorizontalBox)
					+ SHorizontalBox::Slot()
					.HAlign(HAlign_Fill)
					[
						NestedTree.ToSharedRef()
					]
					+ SHorizontalBox::Slot()
					.HAlign(HAlign_Right)
					.AutoWidth()
					[
						SNew(SBox)
						.WidthOverride(16.0f)
						[
							ExternalScrollbar.ToSharedRef()
						]
					]
					
				]
				
			]
		];

		HeaderBox->AddSlot()
			.FillWidth(1.0f)
			[
				SNullWidget::NullWidget
			];
	}
	else
	{
		this->ChildSlot
			[
				SNew(SBox)
				.Padding(10.0f)
				.HAlign(HAlign_Center)
				[
					SNew(STextBlock)
					.Text(LOCTEXT("ConnectMaterialParametersToFillList", "Connect a parameter to see it here."))
				]
			];
	}
}

void SMaterialDynamicParametersPanelWidget::Construct(const FArguments& InArgs)
{
	MaterialInstance = InArgs._InMaterialInstance;
	ExternalScrollbar = SNew(SScrollBar);

	FPropertyEditorModule& PropertyEditorModule = FModuleManager::LoadModuleChecked<FPropertyEditorModule>("PropertyEditor");
	const FPropertyRowGeneratorArgs PropertyRowGeneratorArgs;
	Generator = PropertyEditorModule.CreatePropertyRowGenerator(PropertyRowGeneratorArgs);

	Generator->SetObjects({ MaterialInstance.Get() });

	NestedTree = SNew(SMaterialDynamicParametersOverviewTree)
		.InMaterialInstance(InArgs._InMaterialInstance)
		.InOwner(SharedThis(this))
		.InScrollbar(ExternalScrollbar);

	
	Refresh();
}

void SMaterialDynamicParametersPanelWidget::UpdateInstance(UMaterialInstance* InMaterialInstance)
{
	Generator->SetObjects({ InMaterialInstance });
	NestedTree->MaterialInstance = InMaterialInstance;
	Refresh();
}

#undef LOCTEXT_NAMESPACE
