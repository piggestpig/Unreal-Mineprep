// Copyright Epic Games, Inc. All Rights Reserved.

#include "MineprepBPLibrary.h"
#include "Mineprep.h"

Umineprep::Umineprep(const FObjectInitializer& ObjectInitializer)
: Super(ObjectInitializer)
{

}


float Umineprep::SetEditorUIScale(float Scale)
{
    if (FSlateApplication::IsInitialized())
    {
        if (Scale < 0) return FSlateApplication::Get().GetApplicationScale();
        FSlateApplication::Get().SetApplicationScale(Scale);
    }
    return Scale;
}

void Umineprep::SetTickRunOnAnyThread(UObject* Object, bool bRunOnAnyThread)
{
    if (!Object) return;

    if (AActor* Actor = Cast<AActor>(Object))
    {
        Actor->PrimaryActorTick.bRunOnAnyThread = bRunOnAnyThread;
    }
    else if (UActorComponent* Component = Cast<UActorComponent>(Object))
    {
        Component->PrimaryComponentTick.bRunOnAnyThread = bRunOnAnyThread;
    }
    return;
}

FString Umineprep::GetWidgetTextUnderMouse()
{
    FString ResultText;
    FString TooltipText;
    FString WidgetText;

    if (FSlateApplication::IsInitialized())
    {
        TSharedPtr<SWindow> ActiveWindow = FSlateApplication::Get().GetActiveTopLevelWindow();
        FVector2D MousePos = FSlateApplication::Get().GetCursorPos();

        if (ActiveWindow.IsValid())
        {
            FWidgetPath WidgetPath = FSlateApplication::Get().LocateWindowUnderMouse(
                MousePos, 
                FSlateApplication::Get().GetInteractiveTopLevelWindows(),
                /*bIgnoreEnabledStatus=*/true);

            if (WidgetPath.IsValid())
            {
                for (int32 i = WidgetPath.Widgets.Num() - 1; i >= 0; --i)
                {
                    const FArrangedWidget& ArrangedWidget = WidgetPath.Widgets[i];
                    TSharedRef<SWidget> Widget = ArrangedWidget.Widget;

                    // 先尝试获取当前控件的tooltip
                    TSharedPtr<IToolTip> ToolTip = Widget->GetToolTip();
                    if (ToolTip.IsValid() && !ToolTip->IsEmpty())
                    {
                        if (TSharedPtr<SToolTip> SlateToolTip = StaticCastSharedPtr<SToolTip>(ToolTip))
                        {
                            TooltipText = SlateToolTip->GetTextTooltip().ToString();
                            // 当tooltip为"None"时，当作空字符串
                            if (TooltipText.Equals(TEXT("None")))
                            {
                                TooltipText.Empty();
                            }
                        }
                    }

                    // 检查控件类型并获取文本
                    FString WidgetType = Widget->GetType().ToString();
                    if (WidgetType.Contains(TEXT("SGraphPin")))
                    {
                        // GraphPin的tooltip通常包含了完整的类型信息,所以这里我们优先使用它
                        if (!TooltipText.IsEmpty())
                        {
                            WidgetText = TooltipText;
                            TooltipText.Empty(); // 避免重复显示
                        }
                    }
                    else if (WidgetType.Contains(TEXT("STextBlock")))
                    {
                        if (TSharedPtr<STextBlock> TextBlock = StaticCastSharedRef<STextBlock>(Widget))
                        {
                            WidgetText = TextBlock->GetText().ToString();
                            // 找到文本也不要立即返回,继续向上查找父控件的tooltip
                        }
                    }
                    else if (WidgetType.Contains(TEXT("SButton")))
                    {
                        TSharedPtr<SButton> Button = StaticCastSharedRef<SButton>(Widget);
                        if (TSharedPtr<SWidget> ButtonContent = Button->GetContent())
                        {
                            FString ContentType = ButtonContent->GetType().ToString();
                            if (ContentType.Contains(TEXT("SHorizontalBox")))
                            {
                                if (TSharedPtr<SHorizontalBox> HBox = StaticCastSharedRef<SHorizontalBox>(ButtonContent.ToSharedRef()))
                                {
                                    if (FChildren* Children = HBox->GetChildren())
                                    {
                                        for (int32 ChildIndex = 0; ChildIndex < Children->Num(); ++ChildIndex)
                                        {
                                            TSharedRef<SWidget> Child = Children->GetChildAt(ChildIndex);
                                            FString ChildType = Child->GetType().ToString();
                                            if (ChildType.Contains(TEXT("STextBlock")))
                                            {
                                                if (TSharedPtr<STextBlock> TextBlock = StaticCastSharedRef<STextBlock>(Child))
                                                {
                                                    FString TextBlockText = TextBlock->GetText().ToString();
                                                    if (!TextBlockText.IsEmpty())
                                                    {
                                                        WidgetText = TextBlockText;
                                                        break;  // 跳出内部循环,继续向上查找父控件的tooltip
                                                    }
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                            else if (ContentType.Contains(TEXT("STextBlock")))
                            {
                                if (TSharedPtr<STextBlock> TextBlock = StaticCastSharedRef<STextBlock>(ButtonContent.ToSharedRef()))
                                {
                                    WidgetText = TextBlock->GetText().ToString();
                                }
                            }
                        }
                    }

                    // 如果已经找到了text和tooltip，就可以提前返回了
                    if (!WidgetText.IsEmpty() && !TooltipText.IsEmpty())
                    {
                        // 如果text和tooltip相同,只返回text
                        if (WidgetText.Equals(TooltipText))
                        {
                            return WidgetText;
                        }
                        ResultText = WidgetText + TEXT(" , ") + TooltipText;
                        return ResultText;
                    }
                }

                // 遍历完整个路径后,再组合结果
                if (!WidgetText.IsEmpty() || !TooltipText.IsEmpty())
                {
                    if (!WidgetText.IsEmpty() && !TooltipText.IsEmpty())
                    {
                        // 如果text和tooltip相同,只返回text
                        if (WidgetText.Equals(TooltipText))
                        {
                            ResultText = WidgetText;
                        }
                        else
                        {
                            ResultText = WidgetText + TEXT(" , ") + TooltipText;
                        }
                    }
                    else
                    {
                        ResultText = WidgetText.IsEmpty() ? TooltipText : WidgetText;
                    }
                }
            }
        }
    }
    return ResultText;
}

FComponentMaterialInfo Umineprep::GetMaterialInfo(UMovieSceneComponentMaterialTrack* Track)
{
	if (!Track)
	{
		FFrame::KismetExecutionMessage(TEXT("Cannot call GetMaterialInfo on a null track"), ELogVerbosity::Error);
		return FComponentMaterialInfo();
	}

	return Track->GetMaterialInfo();
}

bool Umineprep::CleanMaterial(UMaterial* Material)
{
	if (!Material)
	{
		return false;
	}

	// 确保MaterialGraph被创建
	if (!Material->MaterialGraph)
	{
		Material->MaterialGraph = CastChecked<UMaterialGraph>(FBlueprintEditorUtils::CreateNewGraph(Material, NAME_None, UMaterialGraph::StaticClass(), UMaterialGraphSchema::StaticClass()));
		Material->MaterialGraph->Material = Material;
	}

	// 在获取未使用节点前先完全重建图表
	Material->MaterialGraph->RebuildGraph();
	
	// 强制更新材质连接关系
	Material->MaterialGraph->LinkMaterialExpressionsFromGraph();

	// 获取所有未使用的节点
	TArray<UEdGraphNode*> UnusedNodes;
	Material->MaterialGraph->GetUnusedExpressions(UnusedNodes);

	if (UnusedNodes.Num() > 0)
	{
		// 创建事务
		const FScopedTransaction Transaction(NSLOCTEXT("Mineprep", "MineprepCleanMaterial", "Clean Unused Material Expressions"));
		
		Material->Modify();
		Material->MaterialGraph->Modify();

		int32 NodesDeleted = 0;
		
		// 删除所有未使用的节点
		for (int32 Index = 0; Index < UnusedNodes.Num(); ++Index)
		{
			if (UMaterialGraphNode* GraphNode = Cast<UMaterialGraphNode>(UnusedNodes[Index]))
			{
				UMaterialExpression* MaterialExpression = GraphNode->MaterialExpression;
				if (!MaterialExpression)
				{
					continue;
				}

				// 删除节点前先断开所有连接
				GraphNode->BreakAllNodeLinks();

				// 删除节点
				FBlueprintEditorUtils::RemoveNode(nullptr, GraphNode, true);

				MaterialExpression->Modify();
				Material->GetExpressionCollection().RemoveExpression(MaterialExpression);
				Material->RemoveExpressionParameter(MaterialExpression);
				MaterialExpression->MarkAsGarbage();
				NodesDeleted++;
			}
		}

		// 重新刷新图表确保所有更改都生效
		Material->MaterialGraph->RebuildGraph();
		Material->MaterialGraph->LinkMaterialExpressionsFromGraph();

		// 标记材质为脏
		Material->MarkPackageDirty();

		// 如果需要,还可以强制刷新材质
		Material->PreEditChange(nullptr);
		Material->PostEditChange();
		
		return NodesDeleted > 0;
	}

	return false;
}

bool Umineprep::SetProjectSetting(const FString& SettingName, const FString& Value)
{
    // 获取Settings模块
    ISettingsModule* SettingsModule = FModuleManager::GetModulePtr<ISettingsModule>("Settings");
    if (!SettingsModule)
    {
        return false;
    }

    // 遍历所有容器
    TArray<FName> ContainerNames;
    SettingsModule->GetContainerNames(ContainerNames);

    for (const FName& ContainerName : ContainerNames)
    {
        TSharedPtr<ISettingsContainer> Container = SettingsModule->GetContainer(ContainerName);
        if (!Container.IsValid())
        {
            continue;
        }

        // 遍历所有类别
        TArray<TSharedPtr<ISettingsCategory>> Categories;
        Container->GetCategories(Categories);

        for (const TSharedPtr<ISettingsCategory>& Category : Categories)
        {
            // 遍历所有分段
            TArray<TSharedPtr<ISettingsSection>> Sections;
            Category->GetSections(Sections);

            for (const TSharedPtr<ISettingsSection>& Section : Sections)
            {
                if (UObject* SectionObj = Section->GetSettingsObject().Get())
                {
                    // 遍历设置对象的所有属性
                    for (TFieldIterator<FProperty> PropIt(SectionObj->GetClass()); PropIt; ++PropIt)
                    {
                        FProperty* Property = *PropIt;
                        if (Property->HasAnyPropertyFlags(CPF_Config) && Property->GetName() == SettingName)
                        {
                            // 创建事务
                            const FScopedTransaction Transaction(NSLOCTEXT("Mineprep", "SetProjectSetting", "Set Project Setting"));
                            
                            // 修改对象
                            SectionObj->Modify();
                            
                            // 设置属性值
                            void* ValuePtr = Property->ContainerPtrToValuePtr<void>(SectionObj);
                            Property->ImportText_Direct(*Value, ValuePtr, SectionObj, 0 );

                            // 通知更改
                            FPropertyChangedEvent ChangeEvent(Property);
                            SectionObj->PostEditChangeProperty(ChangeEvent);
                            
                            // 保存配置到相应的 ini 文件
                            const FString& ConfigFileName = SectionObj->GetDefaultConfigFilename();
                            SectionObj->TryUpdateDefaultConfigFile(ConfigFileName,true);
                            
                            // 调用 SaveConfig() 来确保更改被立即写入
                            SectionObj->SaveConfig();
                            
                            return true;
                        }
                    }
                }
            }
        }
    }
    return false;
}

FString Umineprep::GetProjectSetting(const FString& SettingName)
{
    // 获取Settings模块
    ISettingsModule* SettingsModule = FModuleManager::GetModulePtr<ISettingsModule>("Settings");
    if (!SettingsModule)
    {
        return FString();
    }

    // 遍历所有容器
    TArray<FName> ContainerNames;
    SettingsModule->GetContainerNames(ContainerNames);

    for (const FName& ContainerName : ContainerNames)
    {
        TSharedPtr<ISettingsContainer> Container = SettingsModule->GetContainer(ContainerName);
        if (!Container.IsValid())
        {
            continue;
        }

        // 遍历所有类别
        TArray<TSharedPtr<ISettingsCategory>> Categories;
        Container->GetCategories(Categories);

        for (const TSharedPtr<ISettingsCategory>& Category : Categories)
        {
            //UE_LOG(LogTemp, Display, TEXT("Category Name: %s"), *Category->GetName().ToString());
            // 遍历所有分段
            TArray<TSharedPtr<ISettingsSection>> Sections;
            Category->GetSections(Sections);

            for (const TSharedPtr<ISettingsSection>& Section : Sections)
            {
                //UE_LOG(LogTemp, Display, TEXT("Section Name: %s"), *Section->GetName().ToString());
                if (UObject* SectionObj = Section->GetSettingsObject().Get())
                {
                    // 遍历设置对象的所有属性
                    for (TFieldIterator<FProperty> PropIt(SectionObj->GetClass()); PropIt; ++PropIt)
                    {
                        FProperty* Property = *PropIt;
                        if (Property->HasAnyPropertyFlags(CPF_Config) && Property->GetName() == SettingName)
                        {
                            FString OutString;
                            const void* PropertyValue = Property->ContainerPtrToValuePtr<void>(SectionObj);
                            
                            // 将属性值转换为字符串
                            Property->ExportTextItem_Direct(OutString, PropertyValue, PropertyValue, SectionObj, PPF_None);
                            
                            return OutString;
                        }
                    }
                }
            }
        }
    }
    return FString();
}

void Umineprep::OpenProjectSetting(const FName& ContainerName, const FName& CategoryName, const FName& SectionName)
{
    FModuleManager::LoadModuleChecked<ISettingsModule>("Settings").ShowViewer(ContainerName, CategoryName, SectionName);
}


bool Umineprep::ExposeStructVariables(UUserDefinedStruct* Structure) 
{
    if (!Structure) return false;

    Structure->Modify();
    bool bModified = false;
    for (TFieldIterator<FProperty> PropIt(Structure); PropIt; ++PropIt)
    {
        FProperty* Property = *PropIt;
        // 添加CPF_Interp标志
        Property->SetPropertyFlags(CPF_Interp);
        UE_LOG(LogTemp, Display, TEXT("Property Name: %s"), *PropIt->GetName());
        bModified = true;
    }

    if (bModified)
    {
        Structure->MarkPackageDirty();
        Structure->PostEditChange();
    }
    return bModified;
}

void Umineprep::GatherPropertyNames(UObject* BlueprintObject)
{
    if (!BlueprintObject) return;

    UUserDefinedStruct* UserStruct = Cast<UUserDefinedStruct>(BlueprintObject);
    UBlueprint* Blueprint = Cast<UBlueprint>(BlueprintObject);

    // 处理用户自定义结构体
    if (UserStruct)
    {
        for (TFieldIterator<FProperty> PropIt(UserStruct); PropIt; ++PropIt)
        {
            FProperty* Property = *PropIt;
            if (Property)
            {
                FString PropertyName = Property->GetName();
                // 处理带序列化数字后缀的变量名
                int32 UnderscoreIndex;
                if (PropertyName.FindChar('_', UnderscoreIndex) && PropertyName.Len() > UnderscoreIndex + 2)
                {
                    // 检查下划线后是否跟着一个数字
                    if (PropertyName.Mid(UnderscoreIndex + 1, 1).IsNumeric())
                    {
                        PropertyName = PropertyName.Left(UnderscoreIndex);
                    }
                }
                UE_LOG(LogTemp, Display, TEXT("结构体变量：%s"), *PropertyName);
            }
        }
    }

    // 处理蓝图资产
    else if (Blueprint)
    {
        for (FBPVariableDescription& VarDesc : Blueprint->NewVariables)
        {
            if (VarDesc.PropertyFlags & CPF_DisableEditOnInstance) continue; // 检查变量是否公开
            UE_LOG(LogTemp, Display, TEXT("蓝图变量：%s"), *VarDesc.VarName.ToString());
        }

        for (UEdGraph* FunctionGraph : Blueprint->FunctionGraphs)
        {
            if (!FunctionGraph) continue;

            FString FunctionName = FunctionGraph->GetName();
            UK2Node_FunctionEntry* EntryNode = nullptr;
            for (UEdGraphNode* Node : FunctionGraph->Nodes)
            {
                EntryNode = Cast<UK2Node_FunctionEntry>(Node);
                if (EntryNode) break;
            }

            if (EntryNode)
            {
                if (!EntryNode->MetaData.bCallInEditor) continue; // 检查函数是否可在编辑器中调用
            }
            else continue; // 如果没有入口节点，跳过此函数

            UE_LOG(LogTemp, Display, TEXT("蓝图函数：%s"), *FunctionName);
        }
    }
}


bool Umineprep::InjectDisplayName(UObject* BlueprintObject, const TMap<FString, FString>& PropertyDisplayMap, const bool save, const bool debug)
{
    if (!BlueprintObject)
    {
        UE_LOG(LogTemp, Error, TEXT("蓝图为空！"));
        return false;
    }

    bool bSuccess = false;
    UUserDefinedStruct* UserStruct = Cast<UUserDefinedStruct>(BlueprintObject);
    UBlueprint* Blueprint = Cast<UBlueprint>(BlueprintObject);

    // 处理用户自定义结构体
    if (UserStruct)
    {
        for (TFieldIterator<FProperty> PropIt(UserStruct); PropIt; ++PropIt)
        {
            FProperty* Property = *PropIt;
            if (Property)
            {
                FString PropertyName = Property->GetName();
                // 处理带序列化数字后缀的变量名
                int32 UnderscoreIndex;
                if (PropertyName.FindChar('_', UnderscoreIndex) && PropertyName.Len() > UnderscoreIndex + 2)
                {
                    // 检查下划线后是否跟着一个数字
                    if (PropertyName.Mid(UnderscoreIndex + 1, 1).IsNumeric())
                    {
                        PropertyName = PropertyName.Left(UnderscoreIndex);
                    }
                }

                // 在映射中查找匹配项
                const FString* DisplayNamePtr = PropertyDisplayMap.Find(PropertyName);
                // for (const TPair<FString, FString>& Pair : PropertyDisplayMap)
                // {
                //     if (PropertyName.Contains(Pair.Key, ESearchCase::IgnoreCase))
                //     {
                //         DisplayNamePtr = &Pair.Value;
                //         break;
                //     }
                // }

                if (DisplayNamePtr)
                {
                    static const FName NAME_DisplayName("DisplayName");
                    if (DisplayNamePtr->IsEmpty())
                    {
                        Property->RemoveMetaData(NAME_DisplayName);
                        UE_LOG(LogTemp, Display, TEXT("恢复结构体 '%s' 的默认变量名: '%s'"), *UserStruct->GetName(), *PropertyName);
                    }
                    else
                    {
                        Property->SetMetaData(NAME_DisplayName, FString(**DisplayNamePtr));
                        UE_LOG(LogTemp, Display, TEXT("为结构体 '%s' 注入显示名称: '%s' -> '%s'"), *UserStruct->GetName(), *PropertyName, **DisplayNamePtr);
                    }
                    bSuccess = true;
                }
                else if (debug)
                {
                    UE_LOG(LogTemp, Display, TEXT("结构体变量：%s"), *PropertyName);
                }
            }
        }
    }
    // 处理蓝图资产
    else if (Blueprint)
    {
        for (FBPVariableDescription& VarDesc : Blueprint->NewVariables)
        {
            // 检查变量是否公开
            if (VarDesc.PropertyFlags & CPF_DisableEditOnInstance)
            {
                if (debug)
                {
                    UE_LOG(LogTemp, Display, TEXT("跳过非公开变量: %s"), *VarDesc.VarName.ToString());
                }
                continue;
            }

            // 在映射中查找匹配项
            const FString* DisplayNamePtr = PropertyDisplayMap.Find(VarDesc.VarName.ToString());

            if (DisplayNamePtr)
            {
                if (DisplayNamePtr->IsEmpty())
                {
                    VarDesc.RemoveMetaData(TEXT("DisplayName"));
                    UE_LOG(LogTemp, Display, TEXT("恢复蓝图 '%s' 变量的显示名称: '%s'"), *Blueprint->GetName(), *VarDesc.VarName.ToString());
                }
                else
                {
                    VarDesc.SetMetaData(TEXT("DisplayName"), *DisplayNamePtr);
                    UE_LOG(LogTemp, Display, TEXT("为蓝图 '%s' 变量注入显示名称: '%s' -> '%s'"), *Blueprint->GetName(), *VarDesc.VarName.ToString(), **DisplayNamePtr);
                }
                bSuccess = true;
            }
            else if (debug)
            {
                UE_LOG(LogTemp, Display, TEXT("蓝图变量: %s"), *VarDesc.VarName.ToString());
            }
        }

        // 检查所有蓝图函数
        for (UEdGraph* FunctionGraph : Blueprint->FunctionGraphs)
        {
            if (!FunctionGraph) continue;

            FString FunctionName = FunctionGraph->GetName();
            // 找到函数入口节点，检查函数是否可在编辑器中调用
            UK2Node_FunctionEntry* EntryNode = nullptr;
            for (UEdGraphNode* Node : FunctionGraph->Nodes)
            {
                EntryNode = Cast<UK2Node_FunctionEntry>(Node);
                if (EntryNode) break;
            }

            if (EntryNode)
            {
                // 检查函数是否可在编辑器中调用
                if (!EntryNode->MetaData.bCallInEditor)
                {
                    if (debug)
                    {
                        UE_LOG(LogTemp, Display, TEXT("跳过非编辑器可调用函数: %s"), *FunctionName);
                    }
                    continue;
                }
            }
            else {continue;} // 如果没有入口节点，跳过此函数

            // 在映射中查找匹配项
            const FString* DisplayNamePtr = PropertyDisplayMap.Find(FunctionName);

            if (DisplayNamePtr && EntryNode)
            {
                if (DisplayNamePtr->IsEmpty())
                {
                    EntryNode->MetaData.RemoveMetaData(TEXT("DisplayName"));
                    UE_LOG(LogTemp, Display, TEXT("已恢复蓝图 '%s' 函数的显示名称: '%s'"), *Blueprint->GetName(), *FunctionName);
                }
                else
                {
                    EntryNode->MetaData.SetMetaData(TEXT("DisplayName"), FString(**DisplayNamePtr));
                    UE_LOG(LogTemp, Display, TEXT("为蓝图 '%s' 函数注入显示名称: '%s' -> '%s'"), *Blueprint->GetName(), *FunctionName, **DisplayNamePtr);
                }
                bSuccess = true;
            }
            else if (debug)
            {
                UE_LOG(LogTemp, Display, TEXT("蓝图函数: %s"), *FunctionName);
            }
        }
        if (bSuccess)
        {
            FKismetEditorUtilities::CompileBlueprint(Blueprint, save ? EBlueprintCompileOptions::None : EBlueprintCompileOptions::SkipSave);
        }
    }

    if (debug && !bSuccess)
    {
        UE_LOG(LogTemp, Warning, TEXT("注入失败，在 '%s' 中未找到匹配的属性或函数"), *BlueprintObject->GetName());
    }

    return bSuccess;
}

bool Umineprep::SetPropertyTooltip(UObject* BlueprintObject, const TMap<FString, FString>& PropertyTooltipMap, const bool save, const bool debug)
{
    if (!BlueprintObject)
    {
        UE_LOG(LogTemp, Error, TEXT("蓝图对象为空！"));
        return false;
    }

    bool bSuccess = false;
    UUserDefinedStruct* UserStruct = Cast<UUserDefinedStruct>(BlueprintObject);
    UBlueprint* Blueprint = Cast<UBlueprint>(BlueprintObject);

    // 处理用户自定义结构体
    if (UserStruct)
    {
        for (TFieldIterator<FProperty> PropIt(UserStruct); PropIt; ++PropIt)
        {
            FProperty* Property = *PropIt;
            if (Property)
            {
                FString PropertyName = Property->GetName();
                // 处理带序列化数字后缀的变量名
                int32 UnderscoreIndex;
                if (PropertyName.FindChar('_', UnderscoreIndex) && PropertyName.Len() > UnderscoreIndex + 2)
                {
                    // 检查下划线后是否跟着一个数字
                    if (PropertyName.Mid(UnderscoreIndex + 1, 1).IsNumeric())
                    {
                        PropertyName = PropertyName.Left(UnderscoreIndex);
                    }
                }

                // 在映射中查找匹配项
                const FString* TooltipPtr = PropertyTooltipMap.Find(PropertyName);

                if (TooltipPtr)
                {
                    static const FName NAME_Tooltip("Tooltip");
                    if (TooltipPtr->IsEmpty())
                    {
                        Property->RemoveMetaData(NAME_Tooltip);
                        UE_LOG(LogTemp, Display, TEXT("已恢复结构体 '%s' 中变量 '%s' 的工具提示"), *UserStruct->GetName(), *PropertyName);
                    }
                    else
                    {
                        Property->SetMetaData(NAME_Tooltip, FString(**TooltipPtr));
                        UE_LOG(LogTemp, Display, TEXT("已设置结构体 '%s' 中变量 '%s' 的工具提示为：%s"), *UserStruct->GetName(), *PropertyName, **TooltipPtr);
                    }
                    bSuccess = true;
                }
                else if (debug)
                {
                    UE_LOG(LogTemp, Display, TEXT("结构体变量：%s"), *PropertyName);
                }
            }
        }
    }
    // 处理蓝图资产
    else if (Blueprint)
    {
        // 先检查变量
        for (FBPVariableDescription& VarDesc : Blueprint->NewVariables)
        {
            // 检查变量是否公开
            if (VarDesc.PropertyFlags & CPF_DisableEditOnInstance)
            {
                if (debug)
                {
                    UE_LOG(LogTemp, Display, TEXT("跳过非公开变量: %s"), *VarDesc.VarName.ToString());
                }
                continue;
            }

            // 在映射中查找匹配项
            const FString* TooltipPtr = PropertyTooltipMap.Find(VarDesc.VarName.ToString());

            if (TooltipPtr)
            {
                if (TooltipPtr->IsEmpty())
                {
                    VarDesc.RemoveMetaData(TEXT("Tooltip"));
                    UE_LOG(LogTemp, Display, TEXT("已恢复蓝图 '%s' 中变量 '%s' 的工具提示"), *Blueprint->GetName(), *VarDesc.VarName.ToString());
                }
                else
                {
                    VarDesc.SetMetaData(TEXT("Tooltip"), *TooltipPtr);
                    UE_LOG(LogTemp, Display, TEXT("已设置蓝图 '%s' 中变量 '%s' 的工具提示为：%s"), *Blueprint->GetName(), *VarDesc.VarName.ToString(), **TooltipPtr);
                }
                bSuccess = true;
            }
            else if (debug)
            {
                UE_LOG(LogTemp, Display, TEXT("蓝图变量: %s"), *VarDesc.VarName.ToString());
            }
        }

        // 检查所有蓝图函数
        for (UEdGraph* FunctionGraph : Blueprint->FunctionGraphs)
        {
            if (!FunctionGraph) continue;

            FString FunctionName = FunctionGraph->GetName();
            // 找到函数入口节点
            UK2Node_FunctionEntry* EntryNode = nullptr;
            for (UEdGraphNode* Node : FunctionGraph->Nodes)
            {
                EntryNode = Cast<UK2Node_FunctionEntry>(Node);
                if (EntryNode) break;
            }

            if (EntryNode)
            {
                // 检查函数是否可在编辑器中调用
                if (!EntryNode->MetaData.bCallInEditor)
                {
                    if (debug)
                    {
                        UE_LOG(LogTemp, Display, TEXT("跳过非编辑器可调用函数: %s"), *FunctionName);
                    }
                    continue;
                }
            }
            else {continue;} // 如果没有入口节点，跳过此函数

            // 在映射中查找匹配项
            const FString* TooltipPtr = PropertyTooltipMap.Find(FunctionName);

            if (TooltipPtr && EntryNode)
            {
                if (TooltipPtr->IsEmpty())
                {
                    EntryNode->MetaData.RemoveMetaData(TEXT("Tooltip"));
                    UE_LOG(LogTemp, Display, TEXT("已恢复蓝图 '%s' 函数 '%s' 的工具提示"), *Blueprint->GetName(), *FunctionName);
                }
                else
                {
                    EntryNode->MetaData.SetMetaData(TEXT("Tooltip"), FString(**TooltipPtr));
                    UE_LOG(LogTemp, Display, TEXT("已设置蓝图 '%s' 函数 '%s' 的工具提示为：%s"), *Blueprint->GetName(), *FunctionName, **TooltipPtr);
                }
                bSuccess = true;
            }
            else if (debug)
            {
                UE_LOG(LogTemp, Display, TEXT("蓝图函数: %s"), *FunctionName);
            }
        }

        if (bSuccess)
        {
            FKismetEditorUtilities::CompileBlueprint(Blueprint, save ? EBlueprintCompileOptions::None : EBlueprintCompileOptions::SkipSave);
        }
    }

    return bSuccess;
}
