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

void Umineprep::GetWidgetTextUnderMouse(FString& OutWidgetText, FString& OutTooltipText)
{
    OutWidgetText.Empty();
    OutTooltipText.Empty();

    FString TooltipText;
    FString WidgetText;

    // 辅助 Lambda：打印 FText 的本地化信息
    auto PrintTextLocalizationInfo = [](const FText& Text, const FString& SourceDescription)
    {
        if (Text.IsEmpty()) return;
        
        // 获取本地化信息
        TOptional<FString> Namespace = FTextInspector::GetNamespace(Text);
        TOptional<FString> Key = FTextInspector::GetKey(Text);
        const FString* SourceString = FTextInspector::GetSourceString(Text);
        
        FString DisplayText = Text.ToString();
        FString NamespaceStr = Namespace.IsSet() ? Namespace.GetValue() : TEXT("");
        FString KeyStr = Key.IsSet() ? Key.GetValue() : TEXT("");
        FString SourceStr = SourceString ? *SourceString : TEXT("");
        
        // 检查是否是本地化文本
        bool bIsLocalized = Namespace.IsSet() && Key.IsSet();
        
        UE_LOG(LogTemp, Display, TEXT("========== 本地化文本信息 [%s] =========="), *SourceDescription);
        UE_LOG(LogTemp, Display, TEXT("  显示文本：%s"), *DisplayText);
        UE_LOG(LogTemp, Display, TEXT("  是否本地化：%s"), bIsLocalized ? TEXT("是") : TEXT("否"));
        UE_LOG(LogTemp, Display, TEXT("  Namespace：%s"), *NamespaceStr);
        UE_LOG(LogTemp, Display, TEXT("  Key：%s"), *KeyStr);
        UE_LOG(LogTemp, Display, TEXT("  SourceString：%s"), *SourceStr);
        UE_LOG(LogTemp, Display, TEXT("==========================================="));
    };

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
                            FText TooltipFText = SlateToolTip->GetTextTooltip();
                            TooltipText = TooltipFText.ToString();
                            // 打印 Tooltip 的本地化信息
                            PrintTextLocalizationInfo(TooltipFText, TEXT("Tooltip"));
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
                            FText TextFText = TextBlock->GetText();
                            WidgetText = TextFText.ToString();
                            // 打印 TextBlock 的本地化信息
                            PrintTextLocalizationInfo(TextFText, TEXT("STextBlock"));
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
                                                    FText TextFText = TextBlock->GetText();
                                                    FString TextBlockText = TextFText.ToString();
                                                    if (!TextBlockText.IsEmpty())
                                                    {
                                                        WidgetText = TextBlockText;
                                                        // 打印按钮内部 TextBlock 的本地化信息
                                                        PrintTextLocalizationInfo(TextFText, TEXT("Button内部STextBlock"));
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
                                    FText TextFText = TextBlock->GetText();
                                    WidgetText = TextFText.ToString();
                                    // 打印按钮内部 TextBlock 的本地化信息
                                    PrintTextLocalizationInfo(TextFText, TEXT("Button内部STextBlock"));
                                }
                            }
                        }
                    }

                    // 如果已经找到了text和tooltip，就可以提前返回了
                    if (!WidgetText.IsEmpty() && !TooltipText.IsEmpty())
                    {
                        OutWidgetText = WidgetText;
                        OutTooltipText = TooltipText;
                        return;
                    }
                }

                // 遍历完整个路径后，输出结果
                OutWidgetText = WidgetText;
                OutTooltipText = TooltipText;
            }
        }
    }
}

// 辅助 Lambda：尝试对一个 STextBlock 执行本地化设置，返回是否成功设置
static int32 LocTextBlock(TSharedPtr<STextBlock> TextBlock, const FString& NewText)
{
    if (!TextBlock.IsValid()) return 0;

    if (!NewText.IsEmpty())
    {
        // 直接设置指定文本
        UE_LOG(LogTemp, Display, TEXT("LocWidgetTextUnderMouse: 直接设置 '%s' -> '%s'"), *TextBlock->GetText().ToString(), *NewText);
        TextBlock->SetText(FText::FromString(NewText));
        return 1;
    }

    // NewText 为空：获取当前显示文本，在本地化表中查找
    FString DisplayName = TextBlock->GetText().ToString();
    if (DisplayName.IsEmpty()) return 0;

    FText LocalizedName;
    bool bFound = FText::FindTextInLiveTable_Advanced(
        FTextKey(TEXT("UObjectDisplayNames")),
        FTextKey(*DisplayName),
        LocalizedName,
        &DisplayName);

    if (bFound)
    {
        UE_LOG(LogTemp, Display, TEXT("LocWidgetTextUnderMouse: 本地化成功 '%s' -> '%s'"), *DisplayName, *LocalizedName.ToString());
        TextBlock->SetText(LocalizedName);
        return 1;
    }
    else
    {
        UE_LOG(LogTemp, Warning, TEXT("LocWidgetTextUnderMouse: 未在本地化表中找到 Key='%s'"), *DisplayName);
        return 0;
    }
}

int32 Umineprep::LocWidgetTextUnderMouse(const FString& NewText)
{
    int32 SetCount = 0;
    if (!FSlateApplication::IsInitialized()) return SetCount;

    FVector2D MousePos = FSlateApplication::Get().GetCursorPos();
    FWidgetPath WidgetPath = FSlateApplication::Get().LocateWindowUnderMouse(
        MousePos,
        FSlateApplication::Get().GetInteractiveTopLevelWindows(),
        /*bIgnoreEnabledStatus=*/true);

    if (!WidgetPath.IsValid()) return SetCount;

    for (int32 i = WidgetPath.Widgets.Num() - 1; i >= 0; --i)
    {
        TSharedRef<SWidget> Widget = WidgetPath.Widgets[i].Widget;
        FString WidgetType = Widget->GetType().ToString();

        if (WidgetType.Contains(TEXT("STextBlock")))
        {
            SetCount += LocTextBlock(StaticCastSharedRef<STextBlock>(Widget), NewText);
            break;
        }
        else if (WidgetType.Contains(TEXT("SButton")))
        {
            TSharedPtr<SButton> Button = StaticCastSharedRef<SButton>(Widget);
            if (TSharedPtr<SWidget> Content = Button->GetContent())
            {
                FString ContentType = Content->GetType().ToString();
                if (ContentType.Contains(TEXT("STextBlock")))
                {
                    SetCount += LocTextBlock(StaticCastSharedRef<STextBlock>(Content.ToSharedRef()), NewText);
                    break;
                }
                else if (ContentType.Contains(TEXT("SHorizontalBox")))
                {
                    TSharedPtr<SHorizontalBox> HBox = StaticCastSharedRef<SHorizontalBox>(Content.ToSharedRef());
                    if (FChildren* Children = HBox->GetChildren())
                    {
                        for (int32 j = 0; j < Children->Num(); ++j)
                        {
                            TSharedRef<SWidget> Child = Children->GetChildAt(j);
                            if (Child->GetType().ToString().Contains(TEXT("STextBlock")))
                            {
                                SetCount += LocTextBlock(StaticCastSharedRef<STextBlock>(Child), NewText);
                                break;
                            }
                        }
                    }
                    if (SetCount > 0) break;
                }
            }
        }
    }

    if (SetCount == 0)
    {
        UE_LOG(LogTemp, Warning, TEXT("LocWidgetTextUnderMouse: 鼠标下未找到可设置的文本控件"));
    }
    return SetCount;
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
    }
    return bModified;
}

void Umineprep::GatherPropertyNames(UObject* BlueprintObject, TArray<FString>& OutTypes, TArray<FString>& OutKeys, TArray<FString>& OutSourceStrings)
{
    OutTypes.Empty();
    OutKeys.Empty();
    OutSourceStrings.Empty();

    if (!BlueprintObject) return;

    UUserDefinedStruct* UserStruct = Cast<UUserDefinedStruct>(BlueprintObject);
    UBlueprint* Blueprint = Cast<UBlueprint>(BlueprintObject);
    UUserDefinedEnum* UserEnum = Cast<UUserDefinedEnum>(BlueprintObject);

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

                // 获取用于Polyglot本地化的Key（Namespace固定为"UObjectDisplayNames"）
                FString LocalizationKey = Property->GetFullGroupName(false);
                OutTypes.Add(TEXT("结构体变量"));
                OutKeys.Add(LocalizationKey);
                OutSourceStrings.Add(PropertyName);
            }
        }
    }
    // 处理用户自定义枚举
    else if (UserEnum)
    {
        FString EnumName = UserEnum->GetName();

        // 遍历所有枚举值
        for (int32 i = 0; i < UserEnum->NumEnums() - 1; ++i)  // NumEnums() - 1 排除隐藏的 _MAX 值
        {
            FString DisplayName = UserEnum->GetDisplayNameTextByIndex(i).ToString();
            // 去除空格
            FString KeyName = DisplayName.Replace(TEXT(" "), TEXT(""));

            // 获取枚举值的本地化Key：枚举资产名称.枚举值名称
            FString LocalizationKey = FString::Printf(TEXT("%s.%s"), *EnumName, *KeyName);
            OutTypes.Add(TEXT("枚举值"));
            OutKeys.Add(LocalizationKey);
            OutSourceStrings.Add(DisplayName);
        }
    }
    // 处理材质实例/材质接口
    else if (UMaterialInterface* MatInterface = Cast<UMaterialInterface>(BlueprintObject))
    {
        TArray<FMaterialParameterInfo> ParamInfos;
        TArray<FGuid> ParamGuids;

        // 标量参数
        MatInterface->GetAllScalarParameterInfo(ParamInfos, ParamGuids);
        for (const FMaterialParameterInfo& Info : ParamInfos)
        {
            FString ParamName = Info.Name.ToString();
            OutTypes.Add(TEXT("标量参数"));
            OutKeys.Add(ParamName);
            OutSourceStrings.Add(ParamName);
        }

        // 向量参数
        ParamInfos.Empty(); ParamGuids.Empty();
        MatInterface->GetAllVectorParameterInfo(ParamInfos, ParamGuids);
        for (const FMaterialParameterInfo& Info : ParamInfos)
        {
            FString ParamName = Info.Name.ToString();
            OutTypes.Add(TEXT("向量参数"));
            OutKeys.Add(ParamName);
            OutSourceStrings.Add(ParamName);
        }

        // 纹理参数
        ParamInfos.Empty(); ParamGuids.Empty();
        MatInterface->GetAllTextureParameterInfo(ParamInfos, ParamGuids);
        for (const FMaterialParameterInfo& Info : ParamInfos)
        {
            FString ParamName = Info.Name.ToString();
            OutTypes.Add(TEXT("纹理参数"));
            OutKeys.Add(ParamName);
            OutSourceStrings.Add(ParamName);
        }
    }
    // 处理粒子系统
    else if (UNiagaraSystem* NiagaraSystem = Cast<UNiagaraSystem>(BlueprintObject))
    {
        TArray<FNiagaraVariable> UserParams;
        NiagaraSystem->GetExposedParameters().GetUserParameters(UserParams);
        for (const FNiagaraVariable& Param : UserParams)
        {
            FString ParamName = Param.GetName().ToString();
            OutTypes.Add(TEXT("粒子参数"));
            OutKeys.Add(ParamName);
            OutSourceStrings.Add(ParamName);
        }
    }
    // 处理蓝图资产
    else if (Blueprint)
    {
        // 获取生成的类，用于获取实际的FProperty
        UBlueprintGeneratedClass* GeneratedClass = Cast<UBlueprintGeneratedClass>(Blueprint->GeneratedClass);

        for (FBPVariableDescription& VarDesc : Blueprint->NewVariables)
        {
            if (VarDesc.PropertyFlags & CPF_DisableEditOnInstance) continue; // 检查变量是否公开

            FString LocalizationKey;
            // 尝试从生成的类中获取对应的FProperty以获取准确的Key
            if (GeneratedClass)
            {
                FProperty* Property = GeneratedClass->FindPropertyByName(VarDesc.VarName);
                if (Property)
                {
                    LocalizationKey = Property->GetFullGroupName(false);
                }
            }

            if (LocalizationKey.IsEmpty())
            {
                // 如果无法获取，使用蓝图路径作为备用Key
                LocalizationKey = FString::Printf(TEXT("%s_C.%s"), *Blueprint->GetPathName(), *VarDesc.VarName.ToString());
            }

            OutTypes.Add(TEXT("蓝图变量"));
            OutKeys.Add(LocalizationKey);
            OutSourceStrings.Add(VarDesc.VarName.ToString());
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

            // 函数的Key通常是 "ClassName.FunctionName"
            FString LocalizationKey;
            if (GeneratedClass)
            {
                UFunction* Function = GeneratedClass->FindFunctionByName(FName(*FunctionName));
                if (Function)
                {
                    LocalizationKey = Function->GetFullGroupName(false);
                }
            }

            if (LocalizationKey.IsEmpty())
            {
                LocalizationKey = FString::Printf(TEXT("%s_C.%s"), *Blueprint->GetPathName(), *FunctionName);
            }

            OutTypes.Add(TEXT("蓝图函数"));
            OutKeys.Add(LocalizationKey);
            OutSourceStrings.Add(FunctionName);
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
    // 处理蓝图资产的变量和函数
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

        // 然后检查所有蓝图函数
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


void Umineprep::BindNiagaraParam(UMovieSceneNiagaraParameterTrack* ParameterTrack, FNiagaraVariable Parameter, TArray<uint8> DefaultValueData)
{

    if (ParameterTrack != nullptr)
    {
        UMovieSceneNiagaraVectorParameterTrack *VectorTrack = Cast<UMovieSceneNiagaraVectorParameterTrack>(ParameterTrack);
        if (VectorTrack != nullptr)
        {
            VectorTrack->SetChannelsUsed(DefaultValueData.Num()/sizeof(float));
        }

        ParameterTrack->SetParameter(Parameter);
        ParameterTrack->SetDisplayName(FText::FromName(Parameter.GetName()));
        UMovieSceneSection* ParameterSection = ParameterTrack->CreateNewSection();
        ParameterTrack->SetSectionChannelDefaults(ParameterSection, DefaultValueData);
        ParameterSection->SetRange(TRange<FFrameNumber>::All());
        ParameterTrack->AddSection(*ParameterSection);
    }
}


void Umineprep::SetGlobalGravity(FVector Gravity)
{
    UWorld* World = GWorld;
    FPhysScene* PhysScene = World->GetPhysicsScene();
    PhysScene->SetUpForFrame(
        &Gravity,
        FApp::GetDeltaTime(),
        UPhysicsSettings::Get()->MinPhysicsDeltaTime,
        UPhysicsSettings::Get()->MaxPhysicsDeltaTime,
        UPhysicsSettings::Get()->MaxSubstepDeltaTime,
        UPhysicsSettings::Get()->MaxSubsteps,
        UPhysicsSettings::Get()->bSubstepping
    );
}


void Umineprep::SwitchEditorMode(FName ModeID)
{
	GLevelEditorModeTools().ActivateMode(ModeID);
}

bool Umineprep::IsEditorModeActive(FName ModeID)
{
    return GLevelEditorModeTools().IsModeActive(ModeID);
}

bool Umineprep::ActivateScriptableTool(UBlueprint* ToolBlueprint)
{
    // 0. 验证蓝图并获取 ToolIdentifier
    if (!ToolBlueprint)
    {
        return false;
    }

    // 获取类的完整路径作为 ToolIdentifier
    UClass* GeneratedClass = ToolBlueprint->GeneratedClass;
    FString ToolIdentifier;
    GeneratedClass->GetClassPathName().ToString(ToolIdentifier);
    UE_LOG(LogTemp, Log, TEXT("ActivateScriptableTool: 蓝图 '%s' -> ToolIdentifier: %s"), *ToolBlueprint->GetName(), *ToolIdentifier);

    // 1. 获取 Level Editor 的模式管理器
    FEditorModeTools& ModeTools = GLevelEditorModeTools();
    const FEditorModeID ScriptableToolsModeID = TEXT("EM_ScriptableToolsEditorMode");

    // 2. 激活 Scriptable Tools 模式
    if (!ModeTools.IsModeActive(ScriptableToolsModeID))
    {
        ModeTools.ActivateMode(ScriptableToolsModeID);
    }

    // 3. 获取 Scriptable 模式实例 (UEdMode*)
    UEdMode* ScriptableMode = ModeTools.GetActiveScriptableMode(ScriptableToolsModeID);
    if (!ScriptableMode)
    {
        UE_LOG(LogTemp, Warning, TEXT("ActivateScriptableTool: 无法获取 ScriptableToolsEditorMode 实例"));
        return false;
    }

    // 4. 获取 ToolManager
    UInteractiveToolManager* ToolManager = ScriptableMode->GetToolManager();
    if (!ToolManager)
    {
        UE_LOG(LogTemp, Warning, TEXT("ActivateScriptableTool: 无法获取 ToolManager"));
        return false;
    }

    // 5. 检查是否可以激活工具
    if (!ToolManager->CanActivateTool(EToolSide::Mouse, ToolIdentifier))
    {
        UE_LOG(LogTemp, Warning, TEXT("ActivateScriptableTool: 无法激活工具 '%s'，请确保该蓝图继承自 EditorScriptableTool 并已在 Scriptable Tools 模式中注册"), *ToolIdentifier);
        return false;
    }

    // 6. 选择并激活工具
    if (!ToolManager->SelectActiveToolType(EToolSide::Mouse, ToolIdentifier))
    {
        UE_LOG(LogTemp, Warning, TEXT("ActivateScriptableTool: SelectActiveToolType 失败，ToolIdentifier: %s"), *ToolIdentifier);
        return false;
    }

    bool bActivated = ToolManager->ActivateTool(EToolSide::Mouse);
    if (!bActivated)
    {
        UE_LOG(LogTemp, Warning, TEXT("ActivateScriptableTool: ActivateTool 失败，ToolIdentifier: %s"), *ToolIdentifier);
        return false;
    }

    return true;
}

void Umineprep::ShowEditorNotification(
    const FString& Message,
    const FString& SubText,
    EEditorNotificationState State,
    float Duration,
    bool bUseThrobber)
{
    FNotificationInfo Info(FText::FromString(Message));

    // 次级说明文字
    if (!SubText.IsEmpty())
    {
        Info.SubText = FText::FromString(SubText);
    }

    // 自动消失时间（<=0 则保持直到手动关闭）
    Info.ExpireDuration = Duration > 0.0f ? Duration : 0.0f;
    Info.bFireAndForget = Duration > 0.0f;

    // 是否显示旋转加载动画（仅 Pending 时有意义）
    Info.bUseThrobber = bUseThrobber;

    // 淡出动画时长
    Info.FadeOutDuration = 0.5f;
    Info.FadeInDuration  = 0.2f;

    // 允许点击关闭
    Info.bUseSuccessFailIcons = (State == EEditorNotificationState::Success || State == EEditorNotificationState::Fail);

    TSharedPtr<SNotificationItem> NotificationItem =
        FSlateNotificationManager::Get().AddNotification(Info);

    if (NotificationItem.IsValid())
    {
        SNotificationItem::ECompletionState CompletionState;
        switch (State)
        {
            case EEditorNotificationState::Pending:
                CompletionState = SNotificationItem::CS_Pending;
                break;
            case EEditorNotificationState::Success:
                CompletionState = SNotificationItem::CS_Success;
                break;
            case EEditorNotificationState::Fail:
                CompletionState = SNotificationItem::CS_Fail;
                break;
            default:
                CompletionState = SNotificationItem::CS_None;
                break;
        }
        NotificationItem->SetCompletionState(CompletionState);
    }
}