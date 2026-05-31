#include "AddKeyframes.h"

#include "Mineprep.h"
#include "MineprepSubsystem.h"

#include "Channels/MovieSceneChannelProxy.h"
#include "Channels/MovieSceneFloatChannel.h"
#include "Containers/Ticker.h"
#include "Editor.h"
#include "Framework/Application/SlateApplication.h"
#include "Framework/Commands/UIAction.h"
#include "IDetailKeyframeHandler.h"
#include "IDetailTreeNode.h"
#include "IDetailsView.h"
#include "ILevelSequenceEditorToolkit.h"
#include "ISequencer.h"
#include "KeyPropertyParams.h"
#include "LevelSequence.h"
#include "LevelSequenceEditorBlueprintLibrary.h"
#include "MovieScene.h"
#include "MovieScene/Parameters/MovieSceneNiagaraBoolParameterTrack.h"
#include "MovieScene/Parameters/MovieSceneNiagaraColorParameterTrack.h"
#include "MovieScene/Parameters/MovieSceneNiagaraFloatParameterTrack.h"
#include "MovieScene/Parameters/MovieSceneNiagaraIntegerParameterTrack.h"
#include "MovieScene/Parameters/MovieSceneNiagaraParameterTrack.h"
#include "MovieScene/Parameters/MovieSceneNiagaraVectorParameterTrack.h"
#include "NiagaraComponent.h"
#include "NiagaraSystem.h"
#include "NiagaraTypes.h"
#include "PropertyEditorModule.h"
#include "PropertyHandle.h"
#include "Sections/MovieSceneBoolSection.h"
#include "Sections/MovieSceneColorSection.h"
#include "Sections/MovieSceneFloatSection.h"
#include "Sections/MovieSceneIntegerSection.h"
#include "Selection.h"
#include "Styling/AppStyle.h"
#include "Textures/SlateIcon.h"
#include "Subsystems/AssetEditorSubsystem.h"
#include "Widgets/SWidget.h"
#include "Widgets/SWindow.h"
#include "Widgets/Text/STextBlock.h"

#define LOCTEXT_NAMESPACE "MineprepAddKeyframes"

namespace
{
static const FName GNiagaraKeyedStyleName("Sequencer.KeyedStatus.Keyed");
static const FName GNiagaraUnkeyedStyleName("Sequencer.KeyedStatus.NotKeyed");
static const FName GSequencerAnimatedStyleName("Sequencer.KeyedStatus.Animated");
static const FName GSequencerPartialKeyStyleName("Sequencer.KeyedStatus.PartialKey");
static const FString GNiagaraParamPath(TEXT("/Engine/Transient.StructOnScope:"));

TMap<FString, FText> GPendingParamLocalizations;
bool GLocTickerScheduled = false;
FDelegateHandle GKeyframeExtensionHandle;

enum class EMineprepKeyframePropertyType : uint8
{
    None,
    Niagara,
    ColorGrading,
};

struct FResolvedNiagaraParameterContext
{
    UNiagaraComponent* Component = nullptr;
    FNiagaraVariable Parameter;
    FString ParamType;
    FString ParamName;
    FString ParamValue;
};

static UMineprepSubsystem* GetMineprepSubsystem()
{
    return GEditor ? GEditor->GetEditorSubsystem<UMineprepSubsystem>() : nullptr;
}

static UObject* GetHotkeyObject()
{
    if (UMineprepSubsystem* MineprepSubsystem = GetMineprepSubsystem())
    {
        return MineprepSubsystem->GetHotkeyObject();
    }

    return nullptr;
}

static int32 LocalizeTextBlocksInWidget(const TSharedRef<SWidget>& Widget, const TMap<FString, FText>& LocalizationMap)
{
    int32 Count = 0;
    if (Widget->GetType() == FName("STextBlock"))
    {
        TSharedPtr<STextBlock> TextBlock = StaticCastSharedRef<STextBlock>(Widget);
        FString CurrentText = TextBlock->GetText().ToString();

        if (const FText* NewText = LocalizationMap.Find(CurrentText))
        {
            TextBlock->SetText(*NewText);
            ++Count;
        }
        else if (!CurrentText.IsEmpty())
        {
            FText LocalizedText;
            FString SourceStr = CurrentText;
            const bool bFound = FText::FindTextInLiveTable_Advanced(
                FTextKey(TEXT("UObjectDisplayNames")),
                FTextKey(*CurrentText),
                LocalizedText,
                &SourceStr);

            if (bFound)
            {
                TextBlock->SetText(LocalizedText);
                ++Count;
            }
        }

        return Count;
    }

    if (FChildren* Children = Widget->GetAllChildren())
    {
        for (int32 Index = 0; Index < Children->Num(); ++Index)
        {
            Count += LocalizeTextBlocksInWidget(Children->GetChildAt(Index), LocalizationMap);
        }
    }

    return Count;
}

static void SchedulePendingLocalizations()
{
    if (GPendingParamLocalizations.IsEmpty() || GLocTickerScheduled)
    {
        return;
    }

    GLocTickerScheduled = true;
    FTSTicker::GetCoreTicker().AddTicker(
        FTickerDelegate::CreateLambda([](float) -> bool
        {
            if (FSlateApplication::IsInitialized() && !GPendingParamLocalizations.IsEmpty())
            {
                const TArray<TSharedRef<SWindow>>& TopWindows = FSlateApplication::Get().GetInteractiveTopLevelWindows();
                for (const TSharedRef<SWindow>& Window : TopWindows)
                {
                    LocalizeTextBlocksInWidget(Window, GPendingParamLocalizations);
                }

                GPendingParamLocalizations.Empty();
            }

            GLocTickerScheduled = false;
            return false;
        }),
        0.0f);
}

static void QueueLocalizedParamName(const FString& ParamNameStr)
{
    FText LocalizedParamName;
    FString SourceStr = ParamNameStr;
    const bool bLocFound = FText::FindTextInLiveTable_Advanced(
        FTextKey(TEXT("UObjectDisplayNames")),
        FTextKey(*ParamNameStr),
        LocalizedParamName,
        &SourceStr);

    if (!bLocFound)
    {
        return;
    }

    GPendingParamLocalizations.Add(ParamNameStr, LocalizedParamName);
    SchedulePendingLocalizations();
}

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

static FName GetKeyedStatusStyleName(EPropertyKeyedStatus KeyedStatus)
{
    switch (KeyedStatus)
    {
    case EPropertyKeyedStatus::KeyedInFrame:
        return GNiagaraKeyedStyleName;
    case EPropertyKeyedStatus::KeyedInOtherFrame:
        return GSequencerAnimatedStyleName;
    case EPropertyKeyedStatus::PartiallyKeyed:
        return GSequencerPartialKeyStyleName;
    case EPropertyKeyedStatus::NotKeyed:
    default:
        return GNiagaraUnkeyedStyleName;
    }
}

static bool HasNativeDetailKeyframeHandler(TWeakPtr<IDetailTreeNode> OwnerTreeNode)
{
    TSharedPtr<IDetailTreeNode> OwnerTreeNodePtr = OwnerTreeNode.Pin();
    if (!OwnerTreeNodePtr.IsValid())
    {
        return false;
    }

    TSharedPtr<IDetailsView> DetailsView = OwnerTreeNodePtr->GetNodeDetailsViewSharedPtr();
    return DetailsView.IsValid() && DetailsView->GetKeyframeHandler().IsValid();
}

static bool IsNiagaraPropertyHandle(const TSharedPtr<IPropertyHandle>& PropertyHandle)
{
    if (!PropertyHandle.IsValid())
    {
        return false;
    }

    FProperty* Property = PropertyHandle->GetProperty();
    return Property != nullptr
        && Property->GetPathName().StartsWith(GNiagaraParamPath)
        && Property->GetMetaData(FName("Category")).IsEmpty();
}

static bool IsColorGradingPropertyHandle(const TSharedPtr<IPropertyHandle>& PropertyHandle)
{
    if (!PropertyHandle.IsValid())
    {
        return false;
    }

    FProperty* Property = PropertyHandle->GetProperty();
    if (Property == nullptr || !Property->HasAnyPropertyFlags(CPF_Interp))
    {
        return false;
    }

    const FString Category = Property->GetMetaData(TEXT("Category"));
    return !Property->GetMetaData(TEXT("ColorGradingMode")).IsEmpty()
        || Category.StartsWith(TEXT("Color Grading"))
        || Category.StartsWith(TEXT("Lens|Exposure"));
}

static EPropertyKeyedStatus GetColorGradingPropertyKeyedStatus(const TSharedPtr<IPropertyHandle>& PropertyHandle)
{
    if (!PropertyHandle.IsValid())
    {
        return EPropertyKeyedStatus::NotKeyed;
    }

    TSharedPtr<ISequencer> Sequencer = GetFocusedLevelSequencer();
    return Sequencer.IsValid() ? Sequencer->GetPropertyKeyedStatus(*PropertyHandle) : EPropertyKeyedStatus::NotKeyed;
}

static bool CanKeyColorGradingProperty(const TSharedPtr<IPropertyHandle>& PropertyHandle)
{
    if (!PropertyHandle.IsValid())
    {
        return false;
    }

    TSharedPtr<ISequencer> Sequencer = GetFocusedLevelSequencer();
    if (!Sequencer.IsValid() || Sequencer->IsReadOnly())
    {
        return false;
    }

    const UClass* ObjectClass = PropertyHandle->GetOuterBaseClass();
    return ObjectClass != nullptr && Sequencer->CanKeyProperty(FCanKeyPropertyParams(ObjectClass, *PropertyHandle));
}

static bool KeyColorGradingProperty(const TSharedPtr<IPropertyHandle>& PropertyHandle)
{
    if (!CanKeyColorGradingProperty(PropertyHandle))
    {
        return false;
    }

    TSharedPtr<ISequencer> Sequencer = GetFocusedLevelSequencer();
    if (!Sequencer.IsValid())
    {
        return false;
    }

    TArray<UObject*> Objects;
    PropertyHandle->GetOuterObjects(Objects);

    TArray<UObject*> EachObject;
    EachObject.SetNum(1);

    for (UObject* Object : Objects)
    {
        if (!Object)
        {
            continue;
        }

        EachObject[0] = Object;
        Sequencer->KeyProperty(FKeyPropertyParams(EachObject, *PropertyHandle, ESequencerKeyMode::ManualKeyForced));
    }

    return true;
}

static EMineprepKeyframePropertyType GetKeyframePropertyType(const TSharedPtr<IPropertyHandle>& PropertyHandle)
{
    if (IsNiagaraPropertyHandle(PropertyHandle))
    {
        return EMineprepKeyframePropertyType::Niagara;
    }

    if (IsColorGradingPropertyHandle(PropertyHandle))
    {
        return EMineprepKeyframePropertyType::ColorGrading;
    }

    return EMineprepKeyframePropertyType::None;
}

static bool CanKeyResolvedNiagaraParameter(const FResolvedNiagaraParameterContext& Context)
{
    return Context.Component != nullptr && Context.Parameter.IsValid();
}

template <typename ValueType>
static void CopyValueToByteArray(const ValueType& Value, TArray<uint8>& OutData)
{
    OutData.SetNumUninitialized(sizeof(ValueType));
    FMemory::Memcpy(OutData.GetData(), &Value, sizeof(ValueType));
}

static bool UpdateOrAddFloatKey(FMovieSceneFloatChannel& Channel, const FFrameNumber KeyTime, const float Value)
{
    const int32 ExistingKeyIndex = Channel.GetData().FindKey(KeyTime);
    if (ExistingKeyIndex == INDEX_NONE)
    {
        Channel.GetData().UpdateOrAddKey(KeyTime, FMovieSceneFloatValue(Value));
    }
    else
    {
        Channel.GetData().GetValues()[ExistingKeyIndex].Value = Value;
    }

    return true;
}

static bool CanCreateNiagaraParameterTrack(const FNiagaraVariable& Parameter)
{
    const UScriptStruct* TypeStruct = Parameter.GetType().GetScriptStruct();
    return TypeStruct == FNiagaraBool::StaticStruct()
        || TypeStruct == FNiagaraFloat::StaticStruct()
        || TypeStruct == FNiagaraInt32::StaticStruct()
        || TypeStruct == FNiagaraTypeDefinition::GetVec2Struct()
        || TypeStruct == FNiagaraTypeDefinition::GetVec3Struct()
        || TypeStruct == FNiagaraTypeDefinition::GetVec4Struct()
        || TypeStruct == FNiagaraTypeDefinition::GetPositionStruct()
        || TypeStruct == FNiagaraTypeDefinition::GetColorStruct();
}

static UMovieSceneNiagaraParameterTrack* CreateNiagaraParameterTrack(const FNiagaraVariable& Parameter)
{
    const UScriptStruct* TypeStruct = Parameter.GetType().GetScriptStruct();
    if (TypeStruct == FNiagaraBool::StaticStruct())
    {
        return NewObject<UMovieSceneNiagaraBoolParameterTrack>();
    }

    if (TypeStruct == FNiagaraFloat::StaticStruct())
    {
        return NewObject<UMovieSceneNiagaraFloatParameterTrack>();
    }

    if (TypeStruct == FNiagaraInt32::StaticStruct())
    {
        return NewObject<UMovieSceneNiagaraIntegerParameterTrack>();
    }

    if (TypeStruct == FNiagaraTypeDefinition::GetVec2Struct())
    {
        UMovieSceneNiagaraVectorParameterTrack* VectorTrack = NewObject<UMovieSceneNiagaraVectorParameterTrack>();
        VectorTrack->SetChannelsUsed(2);
        return VectorTrack;
    }

    if (TypeStruct == FNiagaraTypeDefinition::GetVec3Struct() || TypeStruct == FNiagaraTypeDefinition::GetPositionStruct())
    {
        UMovieSceneNiagaraVectorParameterTrack* VectorTrack = NewObject<UMovieSceneNiagaraVectorParameterTrack>();
        VectorTrack->SetChannelsUsed(3);
        return VectorTrack;
    }

    if (TypeStruct == FNiagaraTypeDefinition::GetVec4Struct())
    {
        UMovieSceneNiagaraVectorParameterTrack* VectorTrack = NewObject<UMovieSceneNiagaraVectorParameterTrack>();
        VectorTrack->SetChannelsUsed(4);
        return VectorTrack;
    }

    if (TypeStruct == FNiagaraTypeDefinition::GetColorStruct())
    {
        return NewObject<UMovieSceneNiagaraColorParameterTrack>();
    }

    return nullptr;
}

template <typename ChannelType>
static bool ChannelHasAnyKeys(const ChannelType& Channel)
{
    return Channel.GetData().GetTimes().Num() > 0;
}

static bool ParseNiagaraParameterDefaultValueData(const FNiagaraVariable& Parameter, const FString& ValueString, TArray<uint8>& OutDefaultValueData)
{
    const UScriptStruct* TypeStruct = Parameter.GetType().GetScriptStruct();
    if (!TypeStruct)
    {
        return false;
    }

    if (TypeStruct == FNiagaraBool::StaticStruct())
    {
        const bool bValue = ValueString.ToBool() || ValueString == TEXT("1") || ValueString.Equals(TEXT("true"), ESearchCase::IgnoreCase);
        CopyValueToByteArray(FNiagaraBool(bValue), OutDefaultValueData);
        return true;
    }

    if (TypeStruct == FNiagaraFloat::StaticStruct())
    {
        CopyValueToByteArray(FCString::Atof(*ValueString), OutDefaultValueData);
        return true;
    }

    if (TypeStruct == FNiagaraInt32::StaticStruct())
    {
        CopyValueToByteArray(FCString::Atoi(*ValueString), OutDefaultValueData);
        return true;
    }

    if (TypeStruct == FNiagaraTypeDefinition::GetVec2Struct())
    {
        FVector2f Value(ForceInitToZero);
        if (TypeStruct->ImportText(*ValueString, &Value, nullptr, PPF_None, nullptr, TypeStruct->GetName()) == nullptr)
        {
            return false;
        }

        CopyValueToByteArray(Value, OutDefaultValueData);
        return true;
    }

    if (TypeStruct == FNiagaraTypeDefinition::GetVec3Struct())
    {
        FVector3f Value(ForceInitToZero);
        if (TypeStruct->ImportText(*ValueString, &Value, nullptr, PPF_None, nullptr, TypeStruct->GetName()) == nullptr)
        {
            return false;
        }

        CopyValueToByteArray(Value, OutDefaultValueData);
        return true;
    }

    if (TypeStruct == FNiagaraTypeDefinition::GetVec4Struct())
    {
        FVector4f Value(ForceInitToZero);
        if (TypeStruct->ImportText(*ValueString, &Value, nullptr, PPF_None, nullptr, TypeStruct->GetName()) == nullptr)
        {
            return false;
        }

        CopyValueToByteArray(Value, OutDefaultValueData);
        return true;
    }

    if (TypeStruct == FNiagaraTypeDefinition::GetPositionStruct())
    {
        FNiagaraPosition Value(ForceInitToZero);
        if (TypeStruct->ImportText(*ValueString, &Value, nullptr, PPF_None, nullptr, TypeStruct->GetName()) == nullptr)
        {
            return false;
        }

        CopyValueToByteArray(static_cast<FVector3f>(Value), OutDefaultValueData);
        return true;
    }

    if (TypeStruct == FNiagaraTypeDefinition::GetColorStruct())
    {
        FLinearColor Value(ForceInitToZero);
        if (TypeStruct->ImportText(*ValueString, &Value, nullptr, PPF_None, nullptr, TypeStruct->GetName()) == nullptr)
        {
            return false;
        }

        CopyValueToByteArray(Value, OutDefaultValueData);
        return true;
    }

    return false;
}

static bool AddKeyToNiagaraSection(UMovieSceneSection* Section, const FNiagaraVariable& Parameter, const FString& ValueString, const FFrameNumber KeyTime)
{
    if (!Section)
    {
        return false;
    }

    const UScriptStruct* TypeStruct = Parameter.GetType().GetScriptStruct();
    if (!TypeStruct)
    {
        return false;
    }

    if (TypeStruct == FNiagaraBool::StaticStruct())
    {
        UMovieSceneBoolSection* BoolSection = Cast<UMovieSceneBoolSection>(Section);
        if (!BoolSection)
        {
            return false;
        }

        const bool bValue = ValueString.ToBool() || ValueString == TEXT("1") || ValueString.Equals(TEXT("true"), ESearchCase::IgnoreCase);
        BoolSection->GetChannel().GetData().UpdateOrAddKey(KeyTime, bValue);
        BoolSection->ExpandToFrame(KeyTime);
        return true;
    }

    if (TypeStruct == FNiagaraFloat::StaticStruct())
    {
        UMovieSceneFloatSection* FloatSection = Cast<UMovieSceneFloatSection>(Section);
        if (!FloatSection)
        {
            return false;
        }

        UpdateOrAddFloatKey(FloatSection->GetChannel(), KeyTime, FCString::Atof(*ValueString));
        FloatSection->ExpandToFrame(KeyTime);
        return true;
    }

    if (TypeStruct == FNiagaraInt32::StaticStruct())
    {
        FMovieSceneIntegerChannel* IntegerChannel = Section->GetChannelProxy().GetChannel<FMovieSceneIntegerChannel>(0);
        if (!IntegerChannel)
        {
            return false;
        }

        IntegerChannel->GetData().UpdateOrAddKey(KeyTime, FCString::Atoi(*ValueString));
        Section->ExpandToFrame(KeyTime);
        return true;
    }

    if (TypeStruct == FNiagaraTypeDefinition::GetVec2Struct())
    {
        FVector2f Value(ForceInitToZero);
        if (TypeStruct->ImportText(*ValueString, &Value, nullptr, PPF_None, nullptr, TypeStruct->GetName()) == nullptr)
        {
            return false;
        }

        TArrayView<FMovieSceneFloatChannel*> Channels = Section->GetChannelProxy().GetChannels<FMovieSceneFloatChannel>();
        if (Channels.Num() < 2)
        {
            return false;
        }

        UpdateOrAddFloatKey(*Channels[0], KeyTime, Value.X);
        UpdateOrAddFloatKey(*Channels[1], KeyTime, Value.Y);
        Section->ExpandToFrame(KeyTime);
        return true;
    }

    if (TypeStruct == FNiagaraTypeDefinition::GetVec3Struct())
    {
        FVector3f Value(ForceInitToZero);
        if (TypeStruct->ImportText(*ValueString, &Value, nullptr, PPF_None, nullptr, TypeStruct->GetName()) == nullptr)
        {
            return false;
        }

        TArrayView<FMovieSceneFloatChannel*> Channels = Section->GetChannelProxy().GetChannels<FMovieSceneFloatChannel>();
        if (Channels.Num() < 3)
        {
            return false;
        }

        UpdateOrAddFloatKey(*Channels[0], KeyTime, Value.X);
        UpdateOrAddFloatKey(*Channels[1], KeyTime, Value.Y);
        UpdateOrAddFloatKey(*Channels[2], KeyTime, Value.Z);
        Section->ExpandToFrame(KeyTime);
        return true;
    }

    if (TypeStruct == FNiagaraTypeDefinition::GetPositionStruct())
    {
        FNiagaraPosition Value(ForceInitToZero);
        if (TypeStruct->ImportText(*ValueString, &Value, nullptr, PPF_None, nullptr, TypeStruct->GetName()) == nullptr)
        {
            return false;
        }

        TArrayView<FMovieSceneFloatChannel*> Channels = Section->GetChannelProxy().GetChannels<FMovieSceneFloatChannel>();
        if (Channels.Num() < 3)
        {
            return false;
        }

        UpdateOrAddFloatKey(*Channels[0], KeyTime, Value.X);
        UpdateOrAddFloatKey(*Channels[1], KeyTime, Value.Y);
        UpdateOrAddFloatKey(*Channels[2], KeyTime, Value.Z);
        Section->ExpandToFrame(KeyTime);
        return true;
    }

    if (TypeStruct == FNiagaraTypeDefinition::GetVec4Struct())
    {
        FVector4f Value(ForceInitToZero);
        if (TypeStruct->ImportText(*ValueString, &Value, nullptr, PPF_None, nullptr, TypeStruct->GetName()) == nullptr)
        {
            return false;
        }

        TArrayView<FMovieSceneFloatChannel*> Channels = Section->GetChannelProxy().GetChannels<FMovieSceneFloatChannel>();
        if (Channels.Num() < 4)
        {
            return false;
        }

        UpdateOrAddFloatKey(*Channels[0], KeyTime, Value.X);
        UpdateOrAddFloatKey(*Channels[1], KeyTime, Value.Y);
        UpdateOrAddFloatKey(*Channels[2], KeyTime, Value.Z);
        UpdateOrAddFloatKey(*Channels[3], KeyTime, Value.W);
        Section->ExpandToFrame(KeyTime);
        return true;
    }

    if (TypeStruct == FNiagaraTypeDefinition::GetColorStruct())
    {
        UMovieSceneColorSection* ColorSection = Cast<UMovieSceneColorSection>(Section);
        if (!ColorSection)
        {
            return false;
        }

        FLinearColor Value(ForceInitToZero);
        if (TypeStruct->ImportText(*ValueString, &Value, nullptr, PPF_None, nullptr, TypeStruct->GetName()) == nullptr)
        {
            return false;
        }

        UpdateOrAddFloatKey(ColorSection->GetRedChannel(), KeyTime, Value.R);
        UpdateOrAddFloatKey(ColorSection->GetGreenChannel(), KeyTime, Value.G);
        UpdateOrAddFloatKey(ColorSection->GetBlueChannel(), KeyTime, Value.B);
        UpdateOrAddFloatKey(ColorSection->GetAlphaChannel(), KeyTime, Value.A);
        ColorSection->ExpandToFrame(KeyTime);
        return true;
    }

    return false;
}

static UMovieSceneNiagaraParameterTrack* FindNiagaraParameterTrack(UMovieScene* MovieScene, const FGuid& ObjectBinding, const FNiagaraVariable& Parameter)
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
        UMovieSceneNiagaraParameterTrack* ParameterTrack = Cast<UMovieSceneNiagaraParameterTrack>(Track);
        if (!ParameterTrack)
        {
            continue;
        }

        const FNiagaraVariable& TrackParameter = ParameterTrack->GetParameter();
        if (TrackParameter.GetName() == Parameter.GetName() && TrackParameter.GetType() == Parameter.GetType())
        {
            return ParameterTrack;
        }
    }

    return nullptr;
}

static UMovieSceneSection* FindNiagaraParameterSection(UMovieSceneNiagaraParameterTrack* ParameterTrack)
{
    return ParameterTrack && ParameterTrack->GetAllSections().Num() > 0
        ? ParameterTrack->GetAllSections()[0]
        : nullptr;
}

static bool HasAnyNiagaraParameterKeys(UMovieSceneSection* Section, const FNiagaraVariable& Parameter)
{
    if (!Section)
    {
        return false;
    }

    const UScriptStruct* TypeStruct = Parameter.GetType().GetScriptStruct();
    if (!TypeStruct)
    {
        return false;
    }

    if (TypeStruct == FNiagaraBool::StaticStruct())
    {
        if (const UMovieSceneBoolSection* BoolSection = Cast<UMovieSceneBoolSection>(Section))
        {
            return ChannelHasAnyKeys(BoolSection->GetChannel());
        }

        return false;
    }

    if (TypeStruct == FNiagaraFloat::StaticStruct())
    {
        if (const UMovieSceneFloatSection* FloatSection = Cast<UMovieSceneFloatSection>(Section))
        {
            return ChannelHasAnyKeys(FloatSection->GetChannel());
        }

        return false;
    }

    if (TypeStruct == FNiagaraInt32::StaticStruct())
    {
        if (const FMovieSceneIntegerChannel* IntegerChannel = Section->GetChannelProxy().GetChannel<FMovieSceneIntegerChannel>(0))
        {
            return ChannelHasAnyKeys(*IntegerChannel);
        }

        return false;
    }

    if (TypeStruct == FNiagaraTypeDefinition::GetColorStruct())
    {
        if (const UMovieSceneColorSection* ColorSection = Cast<UMovieSceneColorSection>(Section))
        {
            return ChannelHasAnyKeys(ColorSection->GetRedChannel())
                || ChannelHasAnyKeys(ColorSection->GetGreenChannel())
                || ChannelHasAnyKeys(ColorSection->GetBlueChannel())
                || ChannelHasAnyKeys(ColorSection->GetAlphaChannel());
        }

        return false;
    }

    if (TypeStruct == FNiagaraTypeDefinition::GetVec2Struct()
        || TypeStruct == FNiagaraTypeDefinition::GetVec3Struct()
        || TypeStruct == FNiagaraTypeDefinition::GetVec4Struct()
        || TypeStruct == FNiagaraTypeDefinition::GetPositionStruct())
    {
        TArrayView<FMovieSceneFloatChannel*> Channels = Section->GetChannelProxy().GetChannels<FMovieSceneFloatChannel>();
        for (FMovieSceneFloatChannel* Channel : Channels)
        {
            if (Channel && ChannelHasAnyKeys(*Channel))
            {
                return true;
            }
        }
    }

    return false;
}

static bool TryGetNiagaraScalarValueString(TSharedPtr<IPropertyHandle> PropertyHandle, const FNiagaraVariable& Parameter, FString& OutValue)
{
    if (!PropertyHandle.IsValid())
    {
        return false;
    }

    const UScriptStruct* TypeStruct = Parameter.GetType().GetScriptStruct();
    if (!TypeStruct)
    {
        return false;
    }

    TArray<const void*> RawData;
    PropertyHandle->AccessRawData(RawData);

    const void* ValueData = nullptr;
    for (const void* RawValue : RawData)
    {
        if (RawValue)
        {
            ValueData = RawValue;
            break;
        }
    }

    if (!ValueData)
    {
        return false;
    }

    if (TypeStruct == FNiagaraFloat::StaticStruct())
    {
        const FNiagaraFloat* NiagaraFloat = reinterpret_cast<const FNiagaraFloat*>(ValueData);
        OutValue = FString::SanitizeFloat(NiagaraFloat->Value);
        return true;
    }

    if (TypeStruct == FNiagaraInt32::StaticStruct())
    {
        const FNiagaraInt32* NiagaraInt = reinterpret_cast<const FNiagaraInt32*>(ValueData);
        OutValue = FString::FromInt(NiagaraInt->Value);
        return true;
    }

    if (TypeStruct == FNiagaraBool::StaticStruct())
    {
        const FNiagaraBool* NiagaraBool = reinterpret_cast<const FNiagaraBool*>(ValueData);
        OutValue = NiagaraBool->GetValue() ? TEXT("true") : TEXT("false");
        return true;
    }

    return false;
}

static bool ResolveCurrentNiagaraParameterContext(TSharedPtr<IPropertyHandle> PropertyHandle, FResolvedNiagaraParameterContext& OutContext)
{
    if (!IsNiagaraPropertyHandle(PropertyHandle))
    {
        return false;
    }

    FProperty* Property = PropertyHandle->GetProperty();
    if (!Property)
    {
        return false;
    }

    OutContext.ParamName = PropertyHandle->GetPropertyDisplayName().ToString();
    PropertyHandle->GetValueAsFormattedString(OutContext.ParamValue);
    OutContext.ParamType = Property->GetCPPType();

    USelection* SelectedActors = GEditor ? GEditor->GetSelectedActors() : nullptr;
    if (!SelectedActors)
    {
        return true;
    }

    for (FSelectionIterator Iter(*SelectedActors); Iter; ++Iter)
    {
        AActor* Actor = Cast<AActor>(*Iter);
        if (!Actor)
        {
            continue;
        }

        TArray<UActorComponent*> Components;
        Actor->GetComponents(UNiagaraComponent::StaticClass(), Components);
        if (Components.Num() == 0)
        {
            continue;
        }

        OutContext.Component = Cast<UNiagaraComponent>(Components[0]);
        if (Components.Num() > 1)
        {
            if (USelection* SelectedComponents = GEditor->GetSelectedComponents())
            {
                for (FSelectionIterator CompIter(*SelectedComponents); CompIter; ++CompIter)
                {
                    UNiagaraComponent* SelectedNiagaraComp = Cast<UNiagaraComponent>(*CompIter);
                    if (SelectedNiagaraComp && Components.Contains(SelectedNiagaraComp))
                    {
                        OutContext.Component = SelectedNiagaraComp;
                        break;
                    }
                }
            }
        }

        break;
    }

    if (!OutContext.Component)
    {
        return true;
    }

    UNiagaraSystem* System = OutContext.Component->GetAsset();
    if (!System)
    {
        return true;
    }

    TArray<FNiagaraVariable> ParameterVariables;
    System->GetExposedParameters().GetUserParameters(ParameterVariables);
    for (const FNiagaraVariable& ParamVar : ParameterVariables)
    {
        if (ParamVar.GetName().ToString() == OutContext.ParamName)
        {
            OutContext.Parameter = ParamVar;
            OutContext.ParamType = ParamVar.GetType().GetName();

            FString ScalarValueString;
            if (TryGetNiagaraScalarValueString(PropertyHandle, ParamVar, ScalarValueString))
            {
                OutContext.ParamValue = ScalarValueString;
            }

            return true;
        }
    }

    return true;
}

static void NotifyNiagaraKeyVariable(UObject* TargetObject, UObject* ComponentObject, UMovieSceneTrack* Track, UMovieSceneSection* Section, const FString& ParamType, const FString& ParamName, const FString& ParamValue)
{
    UObject* HotkeyObject = GetHotkeyObject();
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
    Params.Object = ComponentObject;
    Params.Track = Track;
    Params.Section = Section;
    Params.ParamType = ParamType;
    Params.ParamName = ParamName;
    Params.ParamValue = ParamValue;

    HotkeyObject->ProcessEvent(KeyVarFunc, &Params);
}

static bool KeyFocusedNiagaraParameter(UNiagaraComponent* NiagaraComponent, const FNiagaraVariable& Parameter, const FString& ValueString, UMovieSceneNiagaraParameterTrack** OutTrack = nullptr, UMovieSceneSection** OutSection = nullptr)
{
    if (!NiagaraComponent)
    {
        UE_LOG(LogTemp, Warning, TEXT("KeyFocusedNiagaraParameter: NiagaraComponent 为空"));
        return false;
    }

    if (OutTrack)
    {
        *OutTrack = nullptr;
    }

    if (OutSection)
    {
        *OutSection = nullptr;
    }

    TSharedPtr<ISequencer> Sequencer = GetFocusedLevelSequencer();
    if (!Sequencer.IsValid())
    {
        UE_LOG(LogTemp, Warning, TEXT("KeyFocusedNiagaraParameter: 未找到当前激活的 Level Sequence Sequencer"));
        return false;
    }

    UMovieSceneSequence* FocusedSequence = Sequencer->GetFocusedMovieSceneSequence();
    UMovieScene* MovieScene = FocusedSequence ? FocusedSequence->GetMovieScene() : nullptr;
    if (!MovieScene || MovieScene->IsReadOnly())
    {
        UE_LOG(LogTemp, Warning, TEXT("KeyFocusedNiagaraParameter: 当前序列不可编辑"));
        return false;
    }

    TArray<uint8> DefaultValueData;
    if (!ParseNiagaraParameterDefaultValueData(Parameter, ValueString, DefaultValueData))
    {
        UE_LOG(LogTemp, Warning, TEXT("KeyFocusedNiagaraParameter: 不支持的 Niagara 参数类型 '%s'，或值解析失败: %s"), *Parameter.GetType().GetName(), *ValueString);
        return false;
    }

    if (!CanCreateNiagaraParameterTrack(Parameter))
    {
        UE_LOG(LogTemp, Warning, TEXT("KeyFocusedNiagaraParameter: 不支持参数类型 '%s' 的轨道创建"), *Parameter.GetType().GetName());
        return false;
    }

    const FScopedTransaction Transaction(LOCTEXT("MineprepKeyNiagaraParameter", "Key Niagara User Parameter"));
    MovieScene->Modify();

    const FGuid ObjectBinding = Sequencer->GetHandleToObject(NiagaraComponent, true);
    if (!ObjectBinding.IsValid())
    {
        UE_LOG(LogTemp, Warning, TEXT("KeyFocusedNiagaraParameter: 无法为 NiagaraComponent 创建或获取 Sequencer 绑定"));
        return false;
    }

    bool bCreatedTrackOrSection = false;
    UMovieSceneNiagaraParameterTrack* ParameterTrack = FindNiagaraParameterTrack(MovieScene, ObjectBinding, Parameter);
    if (!ParameterTrack)
    {
        ParameterTrack = CreateNiagaraParameterTrack(Parameter);
        if (!ParameterTrack)
        {
            UE_LOG(LogTemp, Warning, TEXT("KeyFocusedNiagaraParameter: 创建 Niagara 参数轨失败"));
            return false;
        }

        MovieScene->AddGivenTrack(ParameterTrack, ObjectBinding);
        ParameterTrack->Modify();
        ParameterTrack->SetParameter(Parameter);
        ParameterTrack->SetDisplayName(FText::FromName(Parameter.GetName()));
        bCreatedTrackOrSection = true;
    }

    UMovieSceneSection* ParameterSection = FindNiagaraParameterSection(ParameterTrack);
    if (!ParameterSection)
    {
        ParameterSection = ParameterTrack->CreateNewSection();
        ParameterSection->Modify();
        ParameterTrack->SetSectionChannelDefaults(ParameterSection, DefaultValueData);
        ParameterSection->SetRange(TRange<FFrameNumber>::All());
        ParameterTrack->AddSection(*ParameterSection);
        bCreatedTrackOrSection = true;
    }

    const FFrameNumber KeyTime = Sequencer->GetLocalTime().Time.FrameNumber;
    ParameterTrack->Modify();
    ParameterSection->Modify();

    if (!AddKeyToNiagaraSection(ParameterSection, Parameter, ValueString, KeyTime))
    {
        UE_LOG(LogTemp, Warning, TEXT("KeyFocusedNiagaraParameter: 向轨道写入关键帧失败，参数: %s"), *Parameter.GetName().ToString());
        return false;
    }

    Sequencer->NotifyMovieSceneDataChanged(
        bCreatedTrackOrSection
            ? EMovieSceneDataChangeType::MovieSceneStructureItemAdded
            : EMovieSceneDataChangeType::TrackValueChanged);

    if (OutTrack)
    {
        *OutTrack = ParameterTrack;
    }

    if (OutSection)
    {
        *OutSection = ParameterSection;
    }

    return true;
}

static FSlateIcon GetKeyframeIcon(TWeakPtr<IDetailTreeNode>, TSharedPtr<IPropertyHandle> PropertyHandle)
{
    const EMineprepKeyframePropertyType PropertyType = GetKeyframePropertyType(PropertyHandle);
    if (PropertyType == EMineprepKeyframePropertyType::ColorGrading)
    {
        return FSlateIcon(FAppStyle::GetAppStyleSetName(), GetKeyedStatusStyleName(GetColorGradingPropertyKeyedStatus(PropertyHandle)));
    }

    FResolvedNiagaraParameterContext Context;
    TSharedPtr<ISequencer> Sequencer = GetFocusedLevelSequencer();
    bool bIsKeyed = false;

    if (Sequencer.IsValid() && ResolveCurrentNiagaraParameterContext(PropertyHandle, Context) && CanKeyResolvedNiagaraParameter(Context))
    {
        UMovieSceneSequence* FocusedSequence = Sequencer->GetFocusedMovieSceneSequence();
        UMovieScene* MovieScene = FocusedSequence ? FocusedSequence->GetMovieScene() : nullptr;
        if (MovieScene)
        {
            const FGuid ObjectBinding = Sequencer->GetHandleToObject(Context.Component, false);
            if (ObjectBinding.IsValid())
            {
                if (UMovieSceneNiagaraParameterTrack* ParameterTrack = FindNiagaraParameterTrack(MovieScene, ObjectBinding, Context.Parameter))
                {
                    if (UMovieSceneSection* ParameterSection = FindNiagaraParameterSection(ParameterTrack))
                    {
                        bIsKeyed = HasAnyNiagaraParameterKeys(ParameterSection, Context.Parameter);
                    }
                }
            }
        }
    }

    return FSlateIcon(FAppStyle::GetAppStyleSetName(), bIsKeyed ? GNiagaraKeyedStyleName : GNiagaraUnkeyedStyleName);
}

static void OnAddKeyframeClicked(TWeakPtr<IDetailTreeNode>, TSharedPtr<IPropertyHandle> PropertyHandle)
{
    const EMineprepKeyframePropertyType PropertyType = GetKeyframePropertyType(PropertyHandle);
    if (PropertyType == EMineprepKeyframePropertyType::ColorGrading)
    {
        if (!KeyColorGradingProperty(PropertyHandle))
        {
            UE_LOG(LogTemp, Warning, TEXT("为 ColorGrading 属性添加关键帧失败: %s"), PropertyHandle.IsValid() && PropertyHandle->GetProperty() ? *PropertyHandle->GetProperty()->GetName() : TEXT("Unknown"));
        }

        return;
    }

    FResolvedNiagaraParameterContext Context;
    if (!ResolveCurrentNiagaraParameterContext(PropertyHandle, Context))
    {
        return;
    }

    UMovieSceneNiagaraParameterTrack* ParameterTrack = nullptr;
    UMovieSceneSection* ParameterSection = nullptr;
    if (CanKeyResolvedNiagaraParameter(Context)
        && !KeyFocusedNiagaraParameter(Context.Component, Context.Parameter, Context.ParamValue, &ParameterTrack, &ParameterSection))
    {
        UE_LOG(LogTemp, Warning, TEXT("为 Niagara 参数添加关键帧失败: %s"), *Context.ParamName);
    }

    NotifyNiagaraKeyVariable(Context.Component ? Context.Component->GetAsset() : nullptr, Context.Component, ParameterTrack, ParameterSection, Context.ParamType, Context.ParamName, Context.ParamValue);
}

static bool IsKeyframeButtonEnabled(TWeakPtr<IDetailTreeNode>)
{
    return GetFocusedLevelSequencer().IsValid();
}

static bool IsKeyframeButtonVisible(TWeakPtr<IDetailTreeNode>, TSharedPtr<IPropertyHandle> PropertyHandle)
{
    const EMineprepKeyframePropertyType PropertyType = GetKeyframePropertyType(PropertyHandle);
    if (PropertyType == EMineprepKeyframePropertyType::ColorGrading)
    {
        return CanKeyColorGradingProperty(PropertyHandle);
    }

    return PropertyType == EMineprepKeyframePropertyType::Niagara;
}

static FText BuildParamTooltip(const FString& ParamNameStr, const TSharedPtr<IPropertyHandle>& PropertyHandle)
{
    UObject* HotkeyObject = GetHotkeyObject();
    if (!HotkeyObject)
    {
        return FText::GetEmpty();
    }

    UFunction* GetTooltipFunc = HotkeyObject->FindFunction(FName("GetMatParamTooltip"));
    if (!GetTooltipFunc)
    {
        return FText::GetEmpty();
    }

    struct FTooltipParams
    {
        FString ParamName;
        FString ReturnValue;
    } Params;

    Params.ParamName = ParamNameStr;
    HotkeyObject->ProcessEvent(GetTooltipFunc, &Params);

    if (Params.ReturnValue.IsEmpty())
    {
        return FText::GetEmpty();
    }

    const FText ParamTooltip = FText::FromString(Params.ReturnValue);
    PropertyHandle->SetToolTipText(ParamTooltip);
    return FText::Format(FText::FromString("{0}{1}"), FText::FromString("\n\n"), ParamTooltip);
}

static void RegisterKeyframeExtensionHandler(const FOnGenerateGlobalRowExtensionArgs& Args, TArray<FPropertyRowExtensionButton>& OutExtensionButtons)
{
    TSharedPtr<IPropertyHandle> PropertyHandle = Args.PropertyHandle;
    const EMineprepKeyframePropertyType PropertyType = GetKeyframePropertyType(PropertyHandle);
    if (PropertyType == EMineprepKeyframePropertyType::None)
    {
        return;
    }

    if (PropertyType == EMineprepKeyframePropertyType::ColorGrading && HasNativeDetailKeyframeHandler(Args.OwnerTreeNode))
    {
        return;
    }

    const FString ParamNameStr = PropertyHandle->GetPropertyDisplayName().ToString();
    QueueLocalizedParamName(ParamNameStr);

    FPropertyRowExtensionButton& CreateKey = OutExtensionButtons.AddDefaulted_GetRef();
    CreateKey.Icon = TAttribute<FSlateIcon>::Create(TAttribute<FSlateIcon>::FGetter::CreateStatic(&GetKeyframeIcon, Args.OwnerTreeNode, PropertyHandle));
    CreateKey.Label = NSLOCTEXT("PropertyEditor", "CreateKey", "Create Key");

    static const FText BaseTooltip = NSLOCTEXT("PropertyEditor", "CreateKeyToolTip", "Add a keyframe for this property.");
    CreateKey.ToolTip = FText::Format(FText::FromString("{0}{1}"), BaseTooltip, BuildParamTooltip(ParamNameStr, PropertyHandle));
    CreateKey.UIAction = FUIAction(
        FExecuteAction::CreateStatic(&OnAddKeyframeClicked, Args.OwnerTreeNode, PropertyHandle),
        FCanExecuteAction::CreateStatic(&IsKeyframeButtonEnabled, Args.OwnerTreeNode),
        FIsActionButtonVisible::CreateStatic(&IsKeyframeButtonVisible, Args.OwnerTreeNode, PropertyHandle));
}
}


////////////////////////////////////////////////////////////////////////


namespace Mineprep::AddKeyframes
{
void Register()
{
    if (GKeyframeExtensionHandle.IsValid())
    {
        return;
    }

    FPropertyEditorModule& PropertyEditorModule = FModuleManager::LoadModuleChecked<FPropertyEditorModule>("PropertyEditor");
    GKeyframeExtensionHandle = PropertyEditorModule.GetGlobalRowExtensionDelegate().AddStatic(&RegisterKeyframeExtensionHandler);
}

void Unregister()
{
    if (!GKeyframeExtensionHandle.IsValid())
    {
        return;
    }

    if (FModuleManager::Get().IsModuleLoaded("PropertyEditor"))
    {
        FPropertyEditorModule& PropertyEditorModule = FModuleManager::GetModuleChecked<FPropertyEditorModule>("PropertyEditor");
        PropertyEditorModule.GetGlobalRowExtensionDelegate().Remove(GKeyframeExtensionHandle);
    }

    GKeyframeExtensionHandle.Reset();
}
}

#undef LOCTEXT_NAMESPACE