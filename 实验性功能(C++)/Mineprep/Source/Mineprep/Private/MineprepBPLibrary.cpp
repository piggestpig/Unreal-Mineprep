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
        FSlateApplication::Get().SetApplicationScale(Scale);
    }
    return Scale;
}

void Umineprep::SetPreviewSelectedCameras(bool bPreview)
{
    if (GEditor)
    {
        ULevelEditorViewportSettings* Settings = GetMutableDefault<ULevelEditorViewportSettings>();
        if (Settings)
        {
            Settings->bPreviewSelectedCameras = bPreview;
            Settings->SaveConfig();
            Settings->PostEditChange();
        }
    }
}

void Umineprep::SetCameraPreviewSize(float PreviewSize)
{
    if (GEditor)
    {
        ULevelEditorViewportSettings* Settings = GetMutableDefault<ULevelEditorViewportSettings>();
        if (Settings)
        {
            Settings->CameraPreviewSize = PreviewSize;
            Settings->SaveConfig();
            Settings->PostEditChange();
        }
    }
}

void Umineprep::SetTickRunOnAnyThread(UObject* Object, bool bRunOnAnyThread)
{
    if (!Object)
    {
        return;
    }

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
