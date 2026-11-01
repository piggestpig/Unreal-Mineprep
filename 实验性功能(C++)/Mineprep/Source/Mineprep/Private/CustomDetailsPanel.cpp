#include "CustomDetailsPanel.h"

#include "Components/InstancedStaticMeshComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "DefaultMovementSet/CharacterMoverComponent.h"
#include "DetailCategoryBuilder.h"
#include "DetailWidgetRow.h"
#include "Editor.h"
#include "DetailLayoutBuilder.h"
#include "GameFramework/Actor.h"
#include "GameFramework/Pawn.h"
#include "IDetailCustomization.h"
#include "IDetailsView.h"
#include "MaterialList.h"
#include "Modules/ModuleManager.h"
#include "PropertyCustomizationHelpers.h"
#include "PropertyEditorModule.h"
#include "ScopedTransaction.h"
#include "UObject/UnrealType.h"
#include "Widgets/Input/SButton.h"
#include "Widgets/SBoxPanel.h"
#include "Widgets/Text/STextBlock.h"

namespace
{
    struct FISMArrayEditFlags
    {
        FProperty* Property;
        bool bOriginallyDisabled;
    };

    TArray<FISMArrayEditFlags> ISMArrayEditFlags;
    FDetailLayoutCallback OriginalISMLayout{};
    FOnGetDetailCustomizationInstance ISMLayoutDelegate;

    struct FISMViewVisibility
    {
        TWeakPtr<IDetailsView> View;
        FIsPropertyVisible Original;
        FIsPropertyVisible Override;
    };

    TArray<FISMViewVisibility> ISMViewVisibility;

    void AllowExpandedISMArrayRows(const TSharedPtr<IDetailsView>& View)
    {
        if (!View.IsValid())
        {
            return;
        }
        ISMViewVisibility.RemoveAll([](const FISMViewVisibility& Entry) { return !Entry.View.IsValid(); });
        FISMViewVisibility* Entry = ISMViewVisibility.FindByPredicate(
            [&View](const FISMViewVisibility& Item) { return Item.View.Pin() == View; });
        const FIsPropertyVisible Original = View->GetIsPropertyVisibleDelegate();
        if (Entry && Original.GetHandle() == Entry->Override.GetHandle())
        {
            return;
        }
        if (!Entry)
        {
            Entry = &ISMViewVisibility.AddDefaulted_GetRef();
        }
        Entry->View = View;
        Entry->Original = Original;
        Entry->Override = FIsPropertyVisible::CreateLambda([Original](const FPropertyAndParent& Property)
        {
            // Level Editor applies its own defaults-only visibility filter even
            // to explicitly added external rows. Exempt only the requested arrays.
            if (Property.Objects.Num() == 1 && ISMArrayEditFlags.ContainsByPredicate(
                [&Property](const FISMArrayEditFlags& Item) { return Item.Property == &Property.Property; }))
            {
                const UInstancedStaticMeshComponent* Component = Cast<UInstancedStaticMeshComponent>(Property.Objects[0].Get());
                if (Component && Component->bForceShowAllInstancesDetails)
                {
                    return true;
                }
            }
            return !Original.IsBound() || Original.Execute(Property);
        });
        View->SetIsPropertyVisibleDelegate(Entry->Override);
    }

    void ApplyISMArrayEditFlags(bool bHide)
    {
        // MarkHiddenByCustomization only hides rows: UE still validates every
        // instance's transform each tick. Defaults-only properties are filtered
        // before those property nodes are created. This does not change the data.
        for (const FISMArrayEditFlags& Entry : ISMArrayEditFlags)
        {
            if (bHide || Entry.bOriginallyDisabled)
            {
                Entry.Property->SetPropertyFlags(CPF_DisableEditOnInstance);
            }
            else
            {
                Entry.Property->ClearPropertyFlags(CPF_DisableEditOnInstance);
            }
        }
    }

    class FMineprepISMDetails : public IDetailCustomization
    {
    public:
        static TSharedRef<IDetailCustomization> MakeInstance()
        {
            return MakeShared<FMineprepISMDetails>();
        }

        virtual void CustomizeDetails(const TSharedPtr<IDetailLayoutBuilder>& DetailBuilder) override
        {
            CachedDetailBuilder = DetailBuilder;
            TArray<TWeakObjectPtr<UObject>> Objects;
            DetailBuilder->GetObjectsBeingCustomized(Objects);
            const bool bEditingTemplate = Objects.ContainsByPredicate([](const TWeakObjectPtr<UObject>& Object)
            {
                return Object.IsValid() && Object->IsTemplate();
            });
            if (bEditingTemplate && OriginalISMLayout.DetailLayoutDelegate.IsBound())
            {
                NativeDetails = OriginalISMLayout.DetailLayoutDelegate.Execute();
                NativeDetails->CustomizeDetails(DetailBuilder);
                return;
            }
            CustomizeDetails(*DetailBuilder);
        }

        virtual void CustomizeDetails(IDetailLayoutBuilder& DetailBuilder) override
        {
            AllowExpandedISMArrayRows(DetailBuilder.GetDetailsViewSharedPtr());
            TArray<TWeakObjectPtr<UObject>> Objects;
            DetailBuilder.GetObjectsBeingCustomized(Objects);
            const FText Label = FindFProperty<FProperty>(
                UInstancedStaticMeshComponent::StaticClass(),
                GET_MEMBER_NAME_CHECKED(UInstancedStaticMeshComponent, PerInstanceSMData))->GetDisplayNameText();
            const TWeakObjectPtr<UInstancedStaticMeshComponent> Component = Objects.Num() == 1
                ? Cast<UInstancedStaticMeshComponent>(Objects[0].Get()) : nullptr;
            IDetailCategoryBuilder& Category = DetailBuilder.EditCategory(TEXT("Instances"));
            Category.AddCustomRow(Label)
                .NameContent()
                [
                    SNew(STextBlock).Font(IDetailLayoutBuilder::GetDetailFont()).Text(Label)
                ]
                .ValueContent()
                .MinDesiredWidth(280.f)
                [
                    SNew(SHorizontalBox)
                    + SHorizontalBox::Slot().AutoWidth().VAlign(VAlign_Center).Padding(0.f, 0.f, 8.f, 0.f)
                    [
                        SNew(STextBlock).Font(IDetailLayoutBuilder::GetDetailFont())
                        .Text_Lambda([Objects]()
                        {
                            int64 Count = 0;
                            for (const TWeakObjectPtr<UObject>& Object : Objects)
                            {
                                if (const UInstancedStaticMeshComponent* Item = Cast<UInstancedStaticMeshComponent>(Object.Get()))
                                {
                                    Count += Item->GetInstanceCount();
                                }
                            }
                            return FText::AsNumber(Count);
                        })
                    ]
                    + SHorizontalBox::Slot().AutoWidth()
                    [
                        SNew(SButton)
                        .IsEnabled(Component.IsValid())
                        .ToolTipText(NSLOCTEXT("InstancedStaticMeshComponentDetails", "ShowHideAllInstancesTooltip",
                            "Displays per-instance data in the details. Can be very slow when there are lots of instances."))
                        .Text_Lambda([Component]()
                        {
                            const bool bShow = Component.IsValid() && Component->bForceShowAllInstancesDetails;
                            return FText::Format(bShow
                                ? NSLOCTEXT("InstancedStaticMeshComponentDetails", "HideAllInstances", "Hide All {0} Instances")
                                : NSLOCTEXT("InstancedStaticMeshComponentDetails", "ShowAllInstances", "Show All {0} Instances"),
                                FText::AsNumber(Component.IsValid() ? Component->GetInstanceCount() : 0));
                        })
                        .OnClicked_Lambda([Component, WeakBuilder = CachedDetailBuilder]()
                        {
                            if (Component.IsValid())
                            {
                                Component->bForceShowAllInstancesDetails = !Component->bForceShowAllInstancesDetails;
                                if (IDetailLayoutBuilder* Builder = WeakBuilder.Pin().Get())
                                {
                                    Builder->ForceRefreshDetails();
                                }
                            }
                            return FReply::Handled();
                        })
                    ]
                ];

            if (Component.IsValid() && Component->bForceShowAllInstancesDetails)
            {
                // Explicit single-property rows bypass the defaults-only filter.
                // On collapse, rebuilding the layout drops their property trees.
                const TArray<UObject*> SourceObjects{Component.Get()};
                Category.AddExternalObjectProperty(SourceObjects,
                    GET_MEMBER_NAME_CHECKED(UInstancedStaticMeshComponent, PerInstanceSMData));
                Category.AddExternalObjectProperty(SourceObjects,
                    GET_MEMBER_NAME_CHECKED(UInstancedStaticMeshComponent, PerInstanceSMCustomData), EPropertyLocation::Advanced);
            }
        }

    private:
        TWeakPtr<IDetailLayoutBuilder> CachedDetailBuilder;
        TSharedPtr<IDetailCustomization> NativeDetails;
    };

    void RegisterISMDetails(FPropertyEditorModule& PropertyEditorModule)
    {
        if (ISMArrayEditFlags.IsEmpty())
        {
            // Save the native factory and its ordering; do not drop the engine's
            // class-default customization or replace it permanently on shutdown.
            FModuleManager::LoadModuleChecked<IModuleInterface>(TEXT("DetailCustomizations"));
            OriginalISMLayout = PropertyEditorModule.GetClassNameToDetailLayoutNameMap().FindChecked(TEXT("InstancedStaticMeshComponent"));
            for (const FName Name : {
                GET_MEMBER_NAME_CHECKED(UInstancedStaticMeshComponent, PerInstanceSMData),
                GET_MEMBER_NAME_CHECKED(UInstancedStaticMeshComponent, PerInstanceSMCustomData)})
            {
                FProperty* Property = FindFProperty<FProperty>(UInstancedStaticMeshComponent::StaticClass(), Name);
                check(Property);
                ISMArrayEditFlags.Add({Property, Property->HasAnyPropertyFlags(CPF_DisableEditOnInstance)});
            }
            ISMLayoutDelegate = FOnGetDetailCustomizationInstance::CreateStatic(&FMineprepISMDetails::MakeInstance);
            FRegisterCustomClassLayoutParams Params;
            Params.OptionalOrder = OriginalISMLayout.Order;
            PropertyEditorModule.RegisterCustomClassLayout(TEXT("InstancedStaticMeshComponent"), ISMLayoutDelegate, Params);
        }
        ApplyISMArrayEditFlags(true);
    }

    void UnregisterISMDetails()
    {
        for (const FISMViewVisibility& Entry : ISMViewVisibility)
        {
            if (const TSharedPtr<IDetailsView> View = Entry.View.Pin();
                View && View->GetIsPropertyVisibleDelegate().GetHandle() == Entry.Override.GetHandle())
            {
                View->SetIsPropertyVisibleDelegate(Entry.Original);
            }
        }
        ISMViewVisibility.Empty();
        ApplyISMArrayEditFlags(false);
        ISMArrayEditFlags.Empty();
        if (FPropertyEditorModule* PropertyEditorModule = FModuleManager::GetModulePtr<FPropertyEditorModule>(TEXT("PropertyEditor")))
        {
            const FDetailLayoutCallback* Current = PropertyEditorModule->GetClassNameToDetailLayoutNameMap().Find(TEXT("InstancedStaticMeshComponent"));
            if (Current && Current->DetailLayoutDelegate.GetHandle() == ISMLayoutDelegate.GetHandle())
            {
                FRegisterCustomClassLayoutParams Params;
                Params.OptionalOrder = OriginalISMLayout.Order;
                PropertyEditorModule->RegisterCustomClassLayout(TEXT("InstancedStaticMeshComponent"), OriginalISMLayout.DetailLayoutDelegate, Params);
            }
        }
    }

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

    static FText MakeSkeletalMeshCategoryLabel(const FString& ComponentLabel, const bool bShowComponentLabel)
    {
        const FText BaseLabel = NSLOCTEXT("UObjectCategory", "Mesh", "Mesh");

        if (!bShowComponentLabel)
        {
            return BaseLabel;
        }

        return FText::Format(NSLOCTEXT("Mineprep", "MeshWithComponentLabel", "{0} ({1})"), BaseLabel, FText::FromString(ComponentLabel));
    }

    static FText MakeMaterialsCategoryLabel(const FString& ComponentLabel, const bool bShowComponentLabel)
    {
        const FText BaseLabel = NSLOCTEXT("UObjectCategory", "Materials", "Materials");

        if (!bShowComponentLabel)
        {
            return BaseLabel;
        }

        return FText::Format(NSLOCTEXT("Mineprep", "MaterialsWithComponentLabel", "{0} ({1})"), BaseLabel, FText::FromString(ComponentLabel));
    }

    struct FSkeletalMeshComponentGroupsCustomizationOptions
    {
        bool bAlwaysShowComponentLabel = false;
        bool bSortAfterRootMeshCategories = false;
    };

    static TPair<int32, int32> GetMineprepSkeletalMeshCategoryOrder(const FName CategoryName)
    {
        const FString CategoryString = CategoryName.ToString();
        if (CategoryString == TEXT("MineprepSkeletalMesh"))
        {
            return {0, 0};
        }

        if (CategoryString == TEXT("MineprepSkeletalMeshMaterials"))
        {
            return {0, 1};
        }

        if (CategoryString.StartsWith(TEXT("MineprepSkeletalMeshMaterials_")))
        {
            return {FCString::Atoi(*CategoryString.Mid(32)), 1};
        }

        if (CategoryString.StartsWith(TEXT("MineprepSkeletalMesh_")))
        {
            return {FCString::Atoi(*CategoryString.Mid(23)), 0};
        }

        return {MAX_int32, MAX_int32};
    }

    static void SortAdditionalSkeletalMeshCategoriesAfterRoot(IDetailLayoutBuilder& DetailLayout)
    {
        DetailLayout.SortCategories([](const TMap<FName, IDetailCategoryBuilder*>& AllCategoryMap)
        {
            static const FName RootMeshCategoryNames[] = {
                TEXT("Mesh"),
                TEXT("Materials"),
                TEXT("Animation"),
            };

            int32 RootSectionMaxSortOrder = MIN_int32;
            for (const FName& CategoryName : RootMeshCategoryNames)
            {
                if (IDetailCategoryBuilder* const* Category = AllCategoryMap.Find(CategoryName))
                {
                    RootSectionMaxSortOrder = FMath::Max(RootSectionMaxSortOrder, (*Category)->GetSortOrder());
                }
            }

            if (RootSectionMaxSortOrder == MIN_int32)
            {
                RootSectionMaxSortOrder = static_cast<int32>(ECategoryPriority::Default) * 1000;
            }

            TArray<TPair<FName, IDetailCategoryBuilder*>> AdditionalCategories;
            for (const TPair<FName, IDetailCategoryBuilder*>& Pair : AllCategoryMap)
            {
                if (GetMineprepSkeletalMeshCategoryOrder(Pair.Key).Key != MAX_int32)
                {
                    AdditionalCategories.Add(Pair);
                }
            }

            AdditionalCategories.Sort([](const TPair<FName, IDetailCategoryBuilder*>& A, const TPair<FName, IDetailCategoryBuilder*>& B)
            {
                const TPair<int32, int32> OrderA = GetMineprepSkeletalMeshCategoryOrder(A.Key);
                const TPair<int32, int32> OrderB = GetMineprepSkeletalMeshCategoryOrder(B.Key);
                if (OrderA.Key != OrderB.Key)
                {
                    return OrderA.Key < OrderB.Key;
                }

                return OrderA.Value < OrderB.Value;
            });

            int32 NextSortOrder = RootSectionMaxSortOrder + 1;
            for (const TPair<FName, IDetailCategoryBuilder*>& Pair : AdditionalCategories)
            {
                Pair.Value->SetSortOrder(NextSortOrder++);
            }
        });
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

            MaterialCategory = &DetailLayout.EditCategory(*CategoryName, CategoryLabel, ECategoryPriority::Important);
            MaterialCategory->InitiallyCollapsed(false);

            for (const FProperty* Property : TFieldRange<FProperty>(UMeshComponent::StaticClass()))
            {
                if (!ShouldExposeAdvancedMaterialProperty(Property))
                {
                    continue;
                }

                MaterialCategory->AddExternalObjectProperty(GroupObjects, Property->GetFName(), EPropertyLocation::Advanced);
            }

            if (bAnyMaterialsToDisplay)
            {
                FMaterialListDelegates MaterialListDelegates;
                MaterialListDelegates.OnGetMaterials.BindSP(this, &FMineprepComponentMaterialCategory::OnGetMaterialsForView);
                MaterialListDelegates.OnMaterialChanged.BindSP(this, &FMineprepComponentMaterialCategory::OnMaterialChanged);
                MaterialListDelegates.OnGenerateCustomMaterialWidgets.BindSP(this, &FMineprepComponentMaterialCategory::OnGenerateWidgetsForMaterial);

                TSharedRef<FMaterialList> MaterialList = MakeShareable(new FMaterialList(DetailLayout, MaterialListDelegates, TArray<FAssetData>()));
                MaterialCategory->AddCustomBuilder(MaterialList);
                MaterialCategory->SetCategoryVisibility(true);
            }
            else
            {
                MaterialCategory->SetCategoryVisibility(false);
            }
        }

    private:
        void OnGetMaterialsForView(IMaterialListBuilder& MaterialList)
        {
            bool bAnyMaterialsToDisplay = false;

            for (const TWeakObjectPtr<USkeletalMeshComponent>& WeakComponent : SelectedComponents)
            {
                USkeletalMeshComponent* Component = WeakComponent.Get();
                if (!Component)
                {
                    continue;
                }

                const int32 NumMaterials = Component->GetNumMaterials();
                for (int32 MaterialIndex = 0; MaterialIndex < NumMaterials; ++MaterialIndex)
                {
                    MaterialList.AddMaterial(MaterialIndex, Component->GetMaterial(MaterialIndex), true, Component);
                    bAnyMaterialsToDisplay = true;
                }
            }

            if (MaterialCategory)
            {
                MaterialCategory->SetCategoryVisibility(bAnyMaterialsToDisplay);
            }
        }

        void OnMaterialChanged(UMaterialInterface* NewMaterial, UMaterialInterface* PrevMaterial, int32 SlotIndex, bool bReplaceAll)
        {
            FProperty* MaterialProperty = FindFProperty<FProperty>(UMeshComponent::StaticClass(), GET_MEMBER_NAME_CHECKED(UMeshComponent, OverrideMaterials));
            if (!MaterialProperty)
            {
                return;
            }

            const FScopedTransaction Transaction(NSLOCTEXT("Mineprep", "ReplaceComponentUsedMaterial", "Replace component used material"));

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
            for (const TWeakObjectPtr<USkeletalMeshComponent>& WeakComponent : SelectedComponents)
            {
                USkeletalMeshComponent* Component = WeakComponent.Get();
                if (!Component)
                {
                    continue;
                }

                const TArray<FName> SlotNames = Component->GetMaterialSlotNames();
                if (SlotNames.IsValidIndex(MaterialIndex) && SlotNames[MaterialIndex] != NAME_None)
                {
                    return FText::FromName(SlotNames[MaterialIndex]);
                }
            }

            return FText::Format(NSLOCTEXT("Mineprep", "ElementLabel", "Element {0}"), FText::AsNumber(MaterialIndex));
        }

    private:
        FString CategoryName;
        FText CategoryLabel;
        TArray<UObject*> GroupObjects;
        TArray<TWeakObjectPtr<USkeletalMeshComponent>> SelectedComponents;
        IDetailCategoryBuilder* MaterialCategory = nullptr;
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

    static void AddSkeletalMeshComponentToGroups(
        USkeletalMeshComponent* SkeletalMeshComponent,
        TMap<FString, TArray<UObject*>>& ComponentGroups,
        TArray<FString>& ComponentGroupOrder)
    {
        if (!SkeletalMeshComponent)
        {
            return;
        }

        const FString ComponentLabel = SkeletalMeshComponent->GetName();
        TArray<UObject*>& GroupObjects = ComponentGroups.FindOrAdd(ComponentLabel);
        if (GroupObjects.IsEmpty())
        {
            ComponentGroupOrder.Add(ComponentLabel);
        }

        GroupObjects.AddUnique(SkeletalMeshComponent);
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
                AddSkeletalMeshComponentToGroups(SkeletalMeshComponent, ComponentGroups, ComponentGroupOrder);
            }
        }
    }

    static void CollectAdditionalSkeletalMeshes(AActor* Actor, TMap<FString, TArray<UObject*>>& ComponentGroups, TArray<FString>& ComponentGroupOrder)
    {
        if (!Actor)
        {
            return;
        }

        USkeletalMeshComponent* RootSkeletalMeshComponent = Cast<USkeletalMeshComponent>(Actor->GetRootComponent());

        TInlineComponentArray<USkeletalMeshComponent*> SkeletalMeshComponents;
        Actor->GetComponents(SkeletalMeshComponents);

        for (USkeletalMeshComponent* SkeletalMeshComponent : SkeletalMeshComponents)
        {
            if (!SkeletalMeshComponent || SkeletalMeshComponent == RootSkeletalMeshComponent)
            {
                continue;
            }

            AddSkeletalMeshComponentToGroups(SkeletalMeshComponent, ComponentGroups, ComponentGroupOrder);
        }
    }

    static void CustomizeSkeletalMeshComponentGroups(
        IDetailLayoutBuilder& DetailLayout,
        const TMap<FString, TArray<UObject*>>& ComponentGroups,
        const TArray<FString>& ComponentGroupOrder,
        TArray<TSharedPtr<FMineprepComponentMaterialCategory>>& MaterialCategories,
        const FSkeletalMeshComponentGroupsCustomizationOptions& Options = FSkeletalMeshComponentGroupsCustomizationOptions())
    {
        const int32 TotalComponentGroups = ComponentGroupOrder.Num();
        const bool bShowComponentLabel = Options.bAlwaysShowComponentLabel || TotalComponentGroups > 1;

        for (int32 GroupIndex = 0; GroupIndex < TotalComponentGroups; ++GroupIndex)
        {
            const FString& ComponentLabel = ComponentGroupOrder[GroupIndex];
            const TArray<UObject*>* GroupObjects = ComponentGroups.Find(ComponentLabel);
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
                MakeSkeletalMeshCategoryLabel(ComponentLabel, bShowComponentLabel),
                ECategoryPriority::Important);

            SkeletalMeshCategory.InitiallyCollapsed(false);

            const FString MaterialsCategoryName = TotalComponentGroups > 1
                ? FString::Printf(TEXT("MineprepSkeletalMeshMaterials_%d"), GroupIndex)
                : TEXT("MineprepSkeletalMeshMaterials");
            TSharedPtr<FMineprepComponentMaterialCategory> MaterialCategory = MakeShared<FMineprepComponentMaterialCategory>(
                *GroupObjects,
                MaterialsCategoryName,
                MakeMaterialsCategoryLabel(ComponentLabel, bShowComponentLabel));
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

        if (Options.bSortAfterRootMeshCategories)
        {
            SortAdditionalSkeletalMeshCategoriesAfterRoot(DetailLayout);
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

            CustomizeSkeletalMeshComponentGroups(DetailLayout, ComponentGroups, ComponentGroupOrder, MaterialCategories);
        }

    private:
        TArray<TSharedPtr<FMineprepComponentMaterialCategory>> MaterialCategories;
    };

    class FCustomSkeletalMeshActorDetails : public IDetailCustomization
    {
    public:
        static TSharedRef<IDetailCustomization> MakeInstance()
        {
            return MakeShareable(new FCustomSkeletalMeshActorDetails());
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
                AActor* Actor = Cast<AActor>(WeakObject.Get());
                if (!Actor)
                {
                    continue;
                }

                CollectAdditionalSkeletalMeshes(Actor, ComponentGroups, ComponentGroupOrder);
            }

            CustomizeSkeletalMeshComponentGroups(
                DetailLayout,
                ComponentGroups,
                ComponentGroupOrder,
                MaterialCategories,
                FSkeletalMeshComponentGroupsCustomizationOptions{
                    .bAlwaysShowComponentLabel = true,
                    .bSortAfterRootMeshCategories = true,
                });
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
        RegisterISMDetails(PropertyEditorModule);
        PropertyEditorModule.RegisterCustomClassLayout(
            TEXT("Pawn"),
            FOnGetDetailCustomizationInstance::CreateStatic(&FCustomMoverPawnDetails::MakeInstance));
        PropertyEditorModule.RegisterCustomClassLayout(
            TEXT("SkeletalMeshActor"),
            FOnGetDetailCustomizationInstance::CreateStatic(&FCustomSkeletalMeshActorDetails::MakeInstance));
        PropertyEditorModule.NotifyCustomizationModuleChanged();
    }

    void Unregister()
    {
        UnregisterISMDetails();
        if (!FModuleManager::Get().IsModuleLoaded(TEXT("PropertyEditor")))
        {
            return;
        }

        FPropertyEditorModule& PropertyEditorModule = FModuleManager::GetModuleChecked<FPropertyEditorModule>(TEXT("PropertyEditor"));
        PropertyEditorModule.UnregisterCustomClassLayout(TEXT("Pawn"));
        PropertyEditorModule.UnregisterCustomClassLayout(TEXT("SkeletalMeshActor"));
        PropertyEditorModule.NotifyCustomizationModuleChanged();
    }
}
