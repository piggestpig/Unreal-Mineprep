#include "CustomDetailsPanel.h"

#include "Components/SkeletalMeshComponent.h"
#include "DefaultMovementSet/CharacterMoverComponent.h"
#include "DetailCategoryBuilder.h"
#include "Editor.h"
#include "DetailLayoutBuilder.h"
#include "GameFramework/Actor.h"
#include "GameFramework/Pawn.h"
#include "IDetailCustomization.h"
#include "MaterialList.h"
#include "Modules/ModuleManager.h"
#include "PropertyCustomizationHelpers.h"
#include "PropertyEditorModule.h"
#include "ScopedTransaction.h"

namespace
{
    static bool ShouldExposeAdvancedMaterialProperty(const FProperty* Property)
    {
        if (!Property || !Property->HasAnyPropertyFlags(CPF_Edit) || Property->HasAnyPropertyFlags(CPF_Deprecated))
        {
            return false;
        }

        const FName PropertyName = Property->GetFName();
        return PropertyName == GET_MEMBER_NAME_CHECKED(UMeshComponent, OverlayMaterial)
            || PropertyName == GET_MEMBER_NAME_CHECKED(UMeshComponent, OverlayMaterialMaxDrawDistance)
            || PropertyName == GET_MEMBER_NAME_CHECKED(UMeshComponent, MaterialSlotsOverlayMaterial);
    }

    static FString GetTopLevelCategoryName(const FProperty* Property)
    {
        if (!Property)
        {
            return FString();
        }

        FString CategoryName = Property->GetMetaData(TEXT("Category"));
        FString TopLevelCategoryName;
        if (CategoryName.Split(TEXT("|"), &TopLevelCategoryName, nullptr))
        {
            return TopLevelCategoryName;
        }

        return CategoryName;
    }

    static bool IsMainSkeletalMeshCategory(const FString& CategoryName)
    {
        return CategoryName == TEXT("Animation")
            || CategoryName == TEXT("Mesh")
            || CategoryName == TEXT("Collision");
    }

    static bool ShouldExposeSkeletalMeshProperty(const FProperty* Property)
    {
        if (!Property || !Property->HasAnyPropertyFlags(CPF_Edit) || Property->HasAnyPropertyFlags(CPF_Deprecated))
        {
            return false;
        }

        if (Property->HasMetaData(TEXT("DeprecatedProperty")) || Property->GetFName() == TEXT("SkeletalMesh"))
        {
            return false;
        }

        return IsMainSkeletalMeshCategory(GetTopLevelCategoryName(Property));
    }

    static FText MakeSkeletalMeshCategoryLabel(const FString& ComponentLabel, const int32 TotalComponentGroups)
    {
        const FText BaseLabel = NSLOCTEXT("UObjectCategory", "Mesh", "Mesh");

        if (TotalComponentGroups <= 1)
        {
            return BaseLabel;
        }

        return FText::Format(NSLOCTEXT("Mineprep", "MeshWithComponentLabel", "{0} ({1})"), BaseLabel, FText::FromString(ComponentLabel));
    }

    static FText MakeMaterialsCategoryLabel(const FString& ComponentLabel, const int32 TotalComponentGroups)
    {
        const FText BaseLabel = NSLOCTEXT("UObjectCategory", "Materials", "Materials");

        if (TotalComponentGroups <= 1)
        {
            return BaseLabel;
        }

        return FText::Format(NSLOCTEXT("Mineprep", "MaterialsWithComponentLabel", "{0} ({1})"), BaseLabel, FText::FromString(ComponentLabel));
    }

    class FMineprepComponentMaterialCategory : public TSharedFromThis<FMineprepComponentMaterialCategory>
    {
    public:
        FMineprepComponentMaterialCategory(const TArray<UObject*>& InGroupObjects, const FString& InCategoryName, const FText& InCategoryLabel)
            : CategoryName(InCategoryName)
            , CategoryLabel(InCategoryLabel)
        {
            GroupObjects = InGroupObjects;

            for (UObject* Object : InGroupObjects)
            {
                if (USkeletalMeshComponent* SkeletalMeshComponent = Cast<USkeletalMeshComponent>(Object))
                {
                    SelectedComponents.Add(SkeletalMeshComponent);
                }
            }
        }

        void Create(IDetailLayoutBuilder& DetailLayout)
        {
            bool bAnyMaterialsToDisplay = false;
            for (const TWeakObjectPtr<USkeletalMeshComponent>& Component : SelectedComponents)
            {
                if (Component.IsValid() && Component->GetNumMaterials() > 0)
                {
                    bAnyMaterialsToDisplay = true;
                    break;
                }
            }

            IDetailCategoryBuilder& MaterialCategory = DetailLayout.EditCategory(*CategoryName, CategoryLabel, ECategoryPriority::Important);
            MaterialCategory.InitiallyCollapsed(false);

            for (const FProperty* Property : TFieldRange<FProperty>(UMeshComponent::StaticClass()))
            {
                if (!ShouldExposeAdvancedMaterialProperty(Property))
                {
                    continue;
                }

                MaterialCategory.AddExternalObjectProperty(GroupObjects, Property->GetFName(), EPropertyLocation::Advanced);
            }

            USkeletalMeshComponent* RepresentativeComponent = GetRepresentativeComponent();
            if (bAnyMaterialsToDisplay)
            {
                AddBaseMaterialRows(MaterialCategory, DetailLayout, RepresentativeComponent);
                MaterialCategory.SetCategoryVisibility(true);
            }
            else
            {
                MaterialCategory.SetCategoryVisibility(false);
            }
        }

    private:
        USkeletalMeshComponent* GetRepresentativeComponent() const
        {
            for (const TWeakObjectPtr<USkeletalMeshComponent>& WeakComponent : SelectedComponents)
            {
                if (USkeletalMeshComponent* SkeletalMeshComponent = WeakComponent.Get())
                {
                    return SkeletalMeshComponent;
                }
            }

            return nullptr;
        }

        void AddBaseMaterialRows(IDetailCategoryBuilder& MaterialCategory, IDetailLayoutBuilder& DetailLayout, USkeletalMeshComponent* RepresentativeComponent)
        {
            if (!RepresentativeComponent)
            {
                return;
            }

            const TArray<FName> SlotNames = RepresentativeComponent->GetMaterialSlotNames();
            const int32 NumMaterials = RepresentativeComponent->GetNumMaterials();

            for (int32 MaterialIndex = 0; MaterialIndex < NumMaterials; ++MaterialIndex)
            {
                const FName SlotName = SlotNames.IsValidIndex(MaterialIndex) ? SlotNames[MaterialIndex] : NAME_None;
                const FText SlotLabel = SlotName != NAME_None
                    ? FText::FromName(SlotName)
                    : FText::Format(NSLOCTEXT("Mineprep", "ElementLabel", "Element {0}"), FText::AsNumber(MaterialIndex));

                TSharedRef<FMaterialItemView> MaterialItemView = CreateMaterialItemView(
                    RepresentativeComponent->GetMaterial(MaterialIndex),
                    MaterialIndex,
                    RepresentativeComponent,
                    SlotLabel,
                    FOnMaterialChanged::CreateSP(this, &FMineprepComponentMaterialCategory::OnMaterialChanged));

                FDetailWidgetRow& MaterialRow = MaterialCategory.AddCustomRow(SlotLabel);
                MaterialRow.NameContent()[MaterialItemView->CreateNameContent()];
                MaterialRow.ValueContent().MinDesiredWidth(250.0f).MaxDesiredWidth(0.0f)
                [
                    MaterialItemView->CreateValueContent(DetailLayout, TArray<FAssetData>(), RepresentativeComponent)
                ];
            }
        }

        TSharedRef<FMaterialItemView> CreateMaterialItemView(
            UMaterialInterface* Material,
            int32 SlotIndex,
            UActorComponent* Component,
            const FText& SlotLabel,
            FOnMaterialChanged OnMaterialChangedDelegate)
        {
            MaterialWidgetLabels.Add(SlotIndex, SlotLabel);

            FOnGenerateWidgetsForMaterial EmptyNameWidgets;
            FOnGenerateWidgetsForMaterial MaterialWidgets = FOnGenerateWidgetsForMaterial::CreateSP(this, &FMineprepComponentMaterialCategory::OnGenerateWidgetsForMaterial);
            FOnResetMaterialToDefaultClicked ResetToDefault;
            FOnGenerateWidgetsForMaterial ExtraBottomWidgets;

            TSharedRef<FMaterialItemView> MaterialItemView = FMaterialItemView::Create(
                FMaterialListItem(Material, SlotIndex, true, Component),
                OnMaterialChangedDelegate,
                EmptyNameWidgets,
                MaterialWidgets,
                ResetToDefault,
                ExtraBottomWidgets,
                1,
                true);

            MaterialItemViews.Add(MaterialItemView);
            return MaterialItemView;
        }

        void OnMaterialChanged(UMaterialInterface* NewMaterial, UMaterialInterface* PrevMaterial, int32 SlotIndex, bool bReplaceAll)
        {
            FProperty* MaterialProperty = FindFProperty<FProperty>(UMeshComponent::StaticClass(), GET_MEMBER_NAME_CHECKED(UMeshComponent, OverrideMaterials));
            if (!MaterialProperty)
            {
                return;
            }

            const FScopedTransaction Transaction(FText::FromString(TEXT("Replace component used material")));

            for (const TWeakObjectPtr<USkeletalMeshComponent>& WeakComponent : SelectedComponents)
            {
                USkeletalMeshComponent* SkeletalMeshComponent = WeakComponent.Get();
                if (!SkeletalMeshComponent || SlotIndex >= SkeletalMeshComponent->GetNumMaterials())
                {
                    continue;
                }

                UMaterialInterface* CurrentMaterial = SkeletalMeshComponent->GetMaterial(SlotIndex);
                if (!bReplaceAll && CurrentMaterial != PrevMaterial)
                {
                    continue;
                }

                SkeletalMeshComponent->Modify();
                SkeletalMeshComponent->PreEditChange(MaterialProperty);
                SkeletalMeshComponent->SetMaterial(SlotIndex, NewMaterial);

                FPropertyChangedEvent PropertyChangedEvent(MaterialProperty, EPropertyChangeType::ValueSet);
                SkeletalMeshComponent->PostEditChangeProperty(PropertyChangedEvent);
            }

            GEditor->RedrawLevelEditingViewports();
        }

        TSharedRef<SWidget> OnGenerateWidgetsForMaterial(UMaterialInterface* Material, int32 SlotIndex)
        {
            return SNew(SMaterialSlotWidget, SlotIndex, true)
                .MaterialName(this, &FMineprepComponentMaterialCategory::GetMaterialNameText, SlotIndex)
                .IsMaterialSlotNameReadOnly(true)
                .DeleteMaterialSlotVisibility(EVisibility::Collapsed);
        }

        FText GetMaterialNameText(int32 MaterialIndex) const
        {
            if (const FText* SlotLabel = MaterialWidgetLabels.Find(MaterialIndex))
            {
                return *SlotLabel;
            }

            return FText::FromString(FString::Printf(TEXT("Element %d"), MaterialIndex));
        }

    private:
        FString CategoryName;
        FText CategoryLabel;
        TArray<UObject*> GroupObjects;
        TArray<TWeakObjectPtr<USkeletalMeshComponent>> SelectedComponents;
        TArray<TSharedPtr<FMaterialItemView>> MaterialItemViews;
        TMap<int32, FText> MaterialWidgetLabels;
    };

    static void CollectAttachedSkeletalMeshes(USceneComponent* RootComponent, TArray<USkeletalMeshComponent*>& OutComponents)
    {
        if (!RootComponent)
        {
            return;
        }

        if (USkeletalMeshComponent* SkeletalMeshComponent = Cast<USkeletalMeshComponent>(RootComponent))
        {
            OutComponents.AddUnique(SkeletalMeshComponent);
        }

        for (USceneComponent* ChildComponent : RootComponent->GetAttachChildren())
        {
            CollectAttachedSkeletalMeshes(ChildComponent, OutComponents);
        }
    }

    static void ResolveMoverSkeletalMeshesInEditor(UCharacterMoverComponent* MoverComponent, TArray<USkeletalMeshComponent*>& OutComponents)
    {
        if (!MoverComponent)
        {
            return;
        }

        if (USceneComponent* PrimaryVisualComponent = MoverComponent->GetPrimaryVisualComponent())
        {
            CollectAttachedSkeletalMeshes(PrimaryVisualComponent, OutComponents);
        }

        if (OutComponents.IsEmpty())
        {
            if (USceneComponent* UpdatedComponent = MoverComponent->GetUpdatedComponent())
            {
                CollectAttachedSkeletalMeshes(UpdatedComponent, OutComponents);
            }
        }

        if (OutComponents.IsEmpty())
        {
            if (AActor* Owner = MoverComponent->GetOwner())
            {
                TInlineComponentArray<USkeletalMeshComponent*> OwnerSkeletalMeshComponents;
                Owner->GetComponents(OwnerSkeletalMeshComponents);
                for (USkeletalMeshComponent* SkeletalMeshComponent : OwnerSkeletalMeshComponents)
                {
                    OutComponents.AddUnique(SkeletalMeshComponent);
                }
            }
        }
    }

    static void CollectMoverDrivenSkeletalMeshes(APawn* Pawn, TMap<FString, TArray<UObject*>>& ComponentGroups, TArray<FString>& ComponentGroupOrder)
    {
        if (!Pawn)
        {
            return;
        }

        TInlineComponentArray<UCharacterMoverComponent*> MoverComponents;
        Pawn->GetComponents(MoverComponents);

        for (UCharacterMoverComponent* MoverComponent : MoverComponents)
        {
            if (!MoverComponent)
            {
                continue;
            }

            TArray<USkeletalMeshComponent*> SkeletalMeshComponents;
            ResolveMoverSkeletalMeshesInEditor(MoverComponent, SkeletalMeshComponents);

            for (USkeletalMeshComponent* SkeletalMeshComponent : SkeletalMeshComponents)
            {
                if (!SkeletalMeshComponent)
                {
                    continue;
                }

                const FString ComponentLabel = SkeletalMeshComponent->GetName();
                TArray<UObject*>& GroupObjects = ComponentGroups.FindOrAdd(ComponentLabel);
                if (GroupObjects.IsEmpty())
                {
                    ComponentGroupOrder.Add(ComponentLabel);
                }

                GroupObjects.AddUnique(SkeletalMeshComponent);
            }
        }
    }

    class FCustomMoverPawnDetails : public IDetailCustomization
    {
    public:
        static TSharedRef<IDetailCustomization> MakeInstance()
        {
            return MakeShareable(new FCustomMoverPawnDetails());
        }

        virtual void CustomizeDetails(IDetailLayoutBuilder& DetailLayout) override
        {
            MaterialCategories.Reset();

            TArray<TWeakObjectPtr<UObject>> ObjectsBeingCustomized;
            DetailLayout.GetObjectsBeingCustomized(ObjectsBeingCustomized);

            TMap<FString, TArray<UObject*>> ComponentGroups;
            TArray<FString> ComponentGroupOrder;

            for (const TWeakObjectPtr<UObject>& WeakObject : ObjectsBeingCustomized)
            {
                APawn* Pawn = Cast<APawn>(WeakObject.Get());
                if (!Pawn)
                {
                    continue;
                }

                CollectMoverDrivenSkeletalMeshes(Pawn, ComponentGroups, ComponentGroupOrder);
            }

            const int32 TotalComponentGroups = ComponentGroupOrder.Num();
            for (int32 GroupIndex = 0; GroupIndex < TotalComponentGroups; ++GroupIndex)
            {
                const FString& ComponentLabel = ComponentGroupOrder[GroupIndex];
                TArray<UObject*>* GroupObjects = ComponentGroups.Find(ComponentLabel);
                if (!GroupObjects || GroupObjects->IsEmpty())
                {
                    continue;
                }

                const UObject* FirstObject = (*GroupObjects)[0];
                if (!FirstObject)
                {
                    continue;
                }

                const FString CategoryName = TotalComponentGroups > 1
                    ? FString::Printf(TEXT("MineprepSkeletalMesh_%d"), GroupIndex)
                    : TEXT("MineprepSkeletalMesh");

                IDetailCategoryBuilder& SkeletalMeshCategory = DetailLayout.EditCategory(
                    *CategoryName,
                    MakeSkeletalMeshCategoryLabel(ComponentLabel, TotalComponentGroups),
                    ECategoryPriority::Important);

                SkeletalMeshCategory.InitiallyCollapsed(false);

                const FString MaterialsCategoryName = TotalComponentGroups > 1
                    ? FString::Printf(TEXT("MineprepSkeletalMeshMaterials_%d"), GroupIndex)
                    : TEXT("MineprepSkeletalMeshMaterials");
                TSharedPtr<FMineprepComponentMaterialCategory> MaterialCategory = MakeShared<FMineprepComponentMaterialCategory>(
                    *GroupObjects,
                    MaterialsCategoryName,
                    MakeMaterialsCategoryLabel(ComponentLabel, TotalComponentGroups));
                MaterialCategory->Create(DetailLayout);
                MaterialCategories.Add(MaterialCategory);

                for (const FProperty* Property : TFieldRange<FProperty>(FirstObject->GetClass()))
                {
                    if (!ShouldExposeSkeletalMeshProperty(Property))
                    {
                        continue;
                    }

                    const bool bAdvancedDisplay = Property->HasAnyPropertyFlags(CPF_AdvancedDisplay);
                    const EPropertyLocation::Type PropertyLocation = bAdvancedDisplay ? EPropertyLocation::Advanced : EPropertyLocation::Default;
                    SkeletalMeshCategory.AddExternalObjectProperty(*GroupObjects, Property->GetFName(), PropertyLocation);
                }
            }
        }

    private:
        TArray<TSharedPtr<FMineprepComponentMaterialCategory>> MaterialCategories;
    };
}

namespace Mineprep::CustomDetailsPanel
{
    void Register()
    {
        FPropertyEditorModule& PropertyEditorModule = FModuleManager::LoadModuleChecked<FPropertyEditorModule>(TEXT("PropertyEditor"));
        PropertyEditorModule.RegisterCustomClassLayout(
            TEXT("Pawn"),
            FOnGetDetailCustomizationInstance::CreateStatic(&FCustomMoverPawnDetails::MakeInstance));
        PropertyEditorModule.NotifyCustomizationModuleChanged();
    }

    void Unregister()
    {
        if (!FModuleManager::Get().IsModuleLoaded(TEXT("PropertyEditor")))
        {
            return;
        }

        FPropertyEditorModule& PropertyEditorModule = FModuleManager::GetModuleChecked<FPropertyEditorModule>(TEXT("PropertyEditor"));
        PropertyEditorModule.UnregisterCustomClassLayout(TEXT("Pawn"));
        PropertyEditorModule.NotifyCustomizationModuleChanged();
    }
}