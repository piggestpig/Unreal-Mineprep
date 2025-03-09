// // Copyright Epic Games, Inc. All Rights Reserved.

// #include "TempBPLibrary.h"
// #include "Mineprep.h"
// #include "UObject/UnrealType.h"
// #include "Engine/Blueprint.h"
// #include "Engine/BlueprintGeneratedClass.h"
// #include "Kismet2/BlueprintEditorUtils.h"
// #include "Kismet2/KismetEditorUtilities.h"
// #include "K2Node_FunctionEntry.h"
// #include "UObject/Class.h"

// void UTempBPLibrary::GatherPropertyNames(UObject* BlueprintObject)
// {
//     if (!BlueprintObject) return;

//     UUserDefinedStruct* UserStruct = Cast<UUserDefinedStruct>(BlueprintObject);
//     UBlueprint* Blueprint = Cast<UBlueprint>(BlueprintObject);

//     // 处理用户自定义结构体
//     if (UserStruct)
//     {
//         for (TFieldIterator<FProperty> PropIt(UserStruct); PropIt; ++PropIt)
//         {
//             FProperty* Property = *PropIt;
//             if (Property)
//             {
//                 FString PropertyName = Property->GetName();
//                 // 处理带序列化数字后缀的变量名
//                 int32 UnderscoreIndex;
//                 if (PropertyName.FindChar('_', UnderscoreIndex) && PropertyName.Len() > UnderscoreIndex + 2)
//                 {
//                     // 检查下划线后是否跟着一个数字
//                     if (PropertyName.Mid(UnderscoreIndex + 1, 1).IsNumeric())
//                     {
//                         PropertyName = PropertyName.Left(UnderscoreIndex);
//                     }
//                 }
//                 UE_LOG(LogTemp, Display, TEXT("结构体变量：%s"), *PropertyName);
//             }
//         }
//     }

//     // 处理蓝图资产
//     else if (Blueprint)
//     {
//         for (FBPVariableDescription& VarDesc : Blueprint->NewVariables)
//         {
//             if (VarDesc.PropertyFlags & CPF_DisableEditOnInstance) continue; // 检查变量是否公开
//             UE_LOG(LogTemp, Display, TEXT("蓝图变量：%s"), *VarDesc.VarName.ToString());
//         }

//         for (UEdGraph* FunctionGraph : Blueprint->FunctionGraphs)
//         {
//             if (!FunctionGraph) continue;

//             FString FunctionName = FunctionGraph->GetName();
//             UK2Node_FunctionEntry* EntryNode = nullptr;
//             for (UEdGraphNode* Node : FunctionGraph->Nodes)
//             {
//                 EntryNode = Cast<UK2Node_FunctionEntry>(Node);
//                 if (EntryNode) break;
//             }

//             if (EntryNode)
//             {
//                 if (!EntryNode->MetaData.bCallInEditor) continue; // 检查函数是否可在编辑器中调用
//             }
//             else continue; // 如果没有入口节点，跳过此函数

//             UE_LOG(LogTemp, Display, TEXT("蓝图函数：%s"), *FunctionName);
//         }
//     }
// }


// bool UTempBPLibrary::InjectDisplayName(UObject* BlueprintObject, const TMap<FString, FString>& PropertyDisplayMap, const bool save, const bool debug)
// {
//     if (!BlueprintObject)
//     {
//         UE_LOG(LogTemp, Error, TEXT("蓝图为空！"));
//         return false;
//     }

//     bool bSuccess = false;
//     UUserDefinedStruct* UserStruct = Cast<UUserDefinedStruct>(BlueprintObject);
//     UBlueprint* Blueprint = Cast<UBlueprint>(BlueprintObject);

//     // 处理用户自定义结构体
//     if (UserStruct)
//     {
//         for (TFieldIterator<FProperty> PropIt(UserStruct); PropIt; ++PropIt)
//         {
//             FProperty* Property = *PropIt;
//             if (Property)
//             {
//                 FString PropertyName = Property->GetName();
//                 // 处理带序列化数字后缀的变量名
//                 int32 UnderscoreIndex;
//                 if (PropertyName.FindChar('_', UnderscoreIndex) && PropertyName.Len() > UnderscoreIndex + 2)
//                 {
//                     // 检查下划线后是否跟着一个数字
//                     if (PropertyName.Mid(UnderscoreIndex + 1, 1).IsNumeric())
//                     {
//                         PropertyName = PropertyName.Left(UnderscoreIndex);
//                     }
//                 }

//                 const FString* DisplayNamePtr = nullptr;
//                 // 在映射中查找匹配项
//                 for (const TPair<FString, FString>& Pair : PropertyDisplayMap)
//                 {
//                     if (PropertyName.Contains(Pair.Key, ESearchCase::IgnoreCase))
//                     {
//                         DisplayNamePtr = &Pair.Value;
//                         break;
//                     }
//                 }

//                 if (DisplayNamePtr)
//                 {
//                     static const FName NAME_DisplayName("DisplayName");
//                     if (DisplayNamePtr->IsEmpty())
//                     {
//                         Property->RemoveMetaData(NAME_DisplayName);
//                         UE_LOG(LogTemp, Display, TEXT("恢复结构体 '%s' 的默认变量名: '%s'"), *UserStruct->GetName(), *PropertyName);
//                     }
//                     else
//                     {
//                         Property->SetMetaData(NAME_DisplayName, **DisplayNamePtr);
//                         UE_LOG(LogTemp, Display, TEXT("为结构体 '%s' 注入显示名称: '%s' -> '%s'"), *UserStruct->GetName(), *PropertyName, **DisplayNamePtr);
//                     }
//                     bSuccess = true;
//                 }
//                 else if (debug)
//                 {
//                     UE_LOG(LogTemp, Display, TEXT("结构体变量：%s"), *PropertyName);
//                 }
//             }
//         }
//     }
//     // 处理蓝图资产
//     else if (Blueprint)
//     {
//         for (FBPVariableDescription& VarDesc : Blueprint->NewVariables)
//         {
//             // 检查变量是否公开
//             if (VarDesc.PropertyFlags & CPF_DisableEditOnInstance)
//             {
//                 if (debug)
//                 {
//                     UE_LOG(LogTemp, Display, TEXT("跳过非公开变量: %s"), *VarDesc.VarName.ToString());
//                 }
//                 continue;
//             }

//             const FString* DisplayNamePtr = nullptr;
//             // 在映射中查找匹配项
//             for (const TPair<FString, FString>& Pair : PropertyDisplayMap)
//             {
//                 if (VarDesc.VarName.ToString().Contains(Pair.Key, ESearchCase::IgnoreCase))
//                 {
//                     DisplayNamePtr = &Pair.Value;
//                     break;
//                 }
//             }

//             if (DisplayNamePtr)
//             {
//                 if (DisplayNamePtr->IsEmpty())
//                 {
//                     VarDesc.RemoveMetaData(TEXT("DisplayName"));
//                     UE_LOG(LogTemp, Display, TEXT("恢复蓝图 '%s' 变量的显示名称: '%s'"), *Blueprint->GetName(), *VarDesc.VarName.ToString());
//                 }
//                 else
//                 {
//                     VarDesc.SetMetaData(TEXT("DisplayName"), *DisplayNamePtr);
//                     UE_LOG(LogTemp, Display, TEXT("为蓝图 '%s' 变量注入显示名称: '%s' -> '%s'"), *Blueprint->GetName(), *VarDesc.VarName.ToString(), **DisplayNamePtr);
//                 }
//                 bSuccess = true;
//             }
//             else if (debug)
//             {
//                 UE_LOG(LogTemp, Display, TEXT("蓝图变量: %s"), *VarDesc.VarName.ToString());
//             }
//         }

//         // 如果没有找到匹配项，则检查函数
//         if (!bSuccess)
//         {
//             // 检查所有蓝图函数
//             for (UEdGraph* FunctionGraph : Blueprint->FunctionGraphs)
//             {
//                 if (!FunctionGraph) continue;

//                 FString FunctionName = FunctionGraph->GetName();
//                 // 找到函数入口节点，检查函数是否可在编辑器中调用
//                 UK2Node_FunctionEntry* EntryNode = nullptr;
//                 for (UEdGraphNode* Node : FunctionGraph->Nodes)
//                 {
//                     EntryNode = Cast<UK2Node_FunctionEntry>(Node);
//                     if (EntryNode) break;
//                 }

//                 if (EntryNode)
//                 {
//                     // 检查函数是否可在编辑器中调用
//                     if (!EntryNode->MetaData.bCallInEditor)
//                     {
//                         if (debug)
//                         {
//                             UE_LOG(LogTemp, Display, TEXT("跳过非编辑器可调用函数: %s"), *FunctionName);
//                         }
//                         continue;
//                     }
//                 }
//                 else {continue;} // 如果没有入口节点，跳过此函数

//                 const FString* DisplayNamePtr = nullptr;
//                 // 在映射中查找匹配项
//                 for (const TPair<FString, FString>& Pair : PropertyDisplayMap)
//                 {
//                     if (FunctionName.Contains(Pair.Key, ESearchCase::IgnoreCase))
//                     {
//                         DisplayNamePtr = &Pair.Value;
//                         break;
//                     }
//                 }

//                 if (DisplayNamePtr && EntryNode)
//                 {
//                     if (DisplayNamePtr->IsEmpty())
//                     {
//                         EntryNode->MetaData.RemoveMetaData(TEXT("DisplayName"));
//                         UE_LOG(LogTemp, Display, TEXT("已恢复蓝图 '%s' 函数的显示名称: '%s'"), *Blueprint->GetName(), *FunctionName);
//                     }
//                     else
//                     {
//                         EntryNode->MetaData.SetMetaData(TEXT("DisplayName"), **DisplayNamePtr);
//                         UE_LOG(LogTemp, Display, TEXT("为蓝图 '%s' 函数注入显示名称: '%s' -> '%s'"), *Blueprint->GetName(), *FunctionName, **DisplayNamePtr);
//                     }
//                     bSuccess = true;
//                 }
//                 else if (debug)
//                 {
//                     UE_LOG(LogTemp, Display, TEXT("蓝图函数: %s"), *FunctionName);
//                 }
//             }
//         }
//     }

//     if (debug && !bSuccess)
//     {
//         UE_LOG(LogTemp, Warning, TEXT("注入失败，在 '%s' 中未找到匹配的属性或函数"), *BlueprintObject->GetName());
//     }
//     if (bSuccess)
//     {
//         FKismetEditorUtilities::CompileBlueprint(Blueprint, save ? EBlueprintCompileOptions::None : EBlueprintCompileOptions::SkipSave);
//     }

//     return bSuccess;
// }

// bool UTempBPLibrary::SetPropertyTooltip(UObject* BlueprintObject, const TMap<FString, FString>& PropertyTooltipMap, const bool save, const bool debug)
// {
//     if (!BlueprintObject)
//     {
//         UE_LOG(LogTemp, Error, TEXT("蓝图对象为空！"));
//         return false;
//     }

//     bool bSuccess = false;
//     UUserDefinedStruct* UserStruct = Cast<UUserDefinedStruct>(BlueprintObject);
//     UBlueprint* Blueprint = Cast<UBlueprint>(BlueprintObject);

//     // 处理用户自定义结构体
//     if (UserStruct)
//     {
//         for (TFieldIterator<FProperty> PropIt(UserStruct); PropIt; ++PropIt)
//         {
//             FProperty* Property = *PropIt;
//             if (Property)
//             {
//                 FString PropertyName = Property->GetName();
//                 // 处理带序列化数字后缀的变量名
//                 int32 UnderscoreIndex;
//                 if (PropertyName.FindChar('_', UnderscoreIndex) && PropertyName.Len() > UnderscoreIndex + 2)
//                 {
//                     // 检查下划线后是否跟着一个数字
//                     if (PropertyName.Mid(UnderscoreIndex + 1, 1).IsNumeric())
//                     {
//                         PropertyName = PropertyName.Left(UnderscoreIndex);
//                     }
//                 }

//                 const FString* TooltipPtr = nullptr;
//                 // 在映射中查找匹配项
//                 for (const TPair<FString, FString>& Pair : PropertyTooltipMap)
//                 {
//                     if (PropertyName.Contains(Pair.Key, ESearchCase::IgnoreCase))
//                     {
//                         TooltipPtr = &Pair.Value;
//                         break;
//                     }
//                 }

//                 if (TooltipPtr)
//                 {
//                     static const FName NAME_Tooltip("Tooltip");
//                     if (TooltipPtr->IsEmpty())
//                     {
//                         Property->RemoveMetaData(NAME_Tooltip);
//                         UE_LOG(LogTemp, Display, TEXT("已恢复结构体 '%s' 中变量 '%s' 的工具提示"), *UserStruct->GetName(), *PropertyName);
//                     }
//                     else
//                     {
//                         Property->SetMetaData(NAME_Tooltip, **TooltipPtr);
//                         UE_LOG(LogTemp, Display, TEXT("已设置结构体 '%s' 中变量 '%s' 的工具提示为：%s"), *UserStruct->GetName(), *PropertyName, **TooltipPtr);
//                     }
//                     bSuccess = true;
//                 }
//                 else if (debug)
//                 {
//                     UE_LOG(LogTemp, Display, TEXT("结构体变量：%s"), *PropertyName);
//                 }
//             }
//         }
//     }
//     // 处理蓝图资产
//     else if (Blueprint)
//     {
//         // 先检查变量
//         for (FBPVariableDescription& VarDesc : Blueprint->NewVariables)
//         {
//             // 检查变量是否公开
//             if (VarDesc.PropertyFlags & CPF_DisableEditOnInstance)
//             {
//                 if (debug)
//                 {
//                     UE_LOG(LogTemp, Display, TEXT("跳过非公开变量: %s"), *VarDesc.VarName.ToString());
//                 }
//                 continue;
//             }

//             const FString* TooltipPtr = nullptr;
//             // 在映射中查找匹配项
//             for (const TPair<FString, FString>& Pair : PropertyTooltipMap)
//             {
//                 if (VarDesc.VarName.ToString().Contains(Pair.Key, ESearchCase::IgnoreCase))
//                 {
//                     TooltipPtr = &Pair.Value;
//                     break;
//                 }
//             }

//             if (TooltipPtr)
//             {
//                 if (TooltipPtr->IsEmpty())
//                 {
//                     VarDesc.RemoveMetaData(TEXT("Tooltip"));
//                     UE_LOG(LogTemp, Display, TEXT("已恢复蓝图 '%s' 中变量 '%s' 的工具提示"), *Blueprint->GetName(), *VarDesc.VarName.ToString());
//                 }
//                 else
//                 {
//                     VarDesc.SetMetaData(TEXT("Tooltip"), *TooltipPtr);
//                     UE_LOG(LogTemp, Display, TEXT("已设置蓝图 '%s' 中变量 '%s' 的工具提示为：%s"), *Blueprint->GetName(), *VarDesc.VarName.ToString(), **TooltipPtr);
//                 }
//                 bSuccess = true;
//             }
//             else if (debug)
//             {
//                 UE_LOG(LogTemp, Display, TEXT("蓝图变量: %s"), *VarDesc.VarName.ToString());
//             }
//         }

//         // 如果没有找到匹配项，则检查函数
//         if (!bSuccess)
//         {
//             // 检查所有蓝图函数
//             for (UEdGraph* FunctionGraph : Blueprint->FunctionGraphs)
//             {
//                 if (!FunctionGraph) continue;

//                 FString FunctionName = FunctionGraph->GetName();
//                 // 找到函数入口节点
//                 UK2Node_FunctionEntry* EntryNode = nullptr;
//                 for (UEdGraphNode* Node : FunctionGraph->Nodes)
//                 {
//                     EntryNode = Cast<UK2Node_FunctionEntry>(Node);
//                     if (EntryNode) break;
//                 }

//                 if (EntryNode)
//                 {
//                     // 检查函数是否可在编辑器中调用
//                     if (!EntryNode->MetaData.bCallInEditor)
//                     {
//                         if (debug)
//                         {
//                             UE_LOG(LogTemp, Display, TEXT("跳过非编辑器可调用函数: %s"), *FunctionName);
//                         }
//                         continue;
//                     }
//                 }
//                 else {continue;} // 如果没有入口节点，跳过此函数

//                 const FString* TooltipPtr = nullptr;
//                 // 在映射中查找匹配项
//                 for (const TPair<FString, FString>& Pair : PropertyTooltipMap)
//                 {
//                     if (FunctionName.Contains(Pair.Key, ESearchCase::IgnoreCase))
//                     {
//                         TooltipPtr = &Pair.Value;
//                         break;
//                     }
//                 }

//                 if (TooltipPtr && EntryNode)
//                 {
//                     if (TooltipPtr->IsEmpty())
//                     {
//                         EntryNode->MetaData.RemoveMetaData(TEXT("Tooltip"));
//                         UE_LOG(LogTemp, Display, TEXT("已恢复蓝图 '%s' 函数 '%s' 的工具提示"), *Blueprint->GetName(), *FunctionName);
//                     }
//                     else
//                     {
//                         EntryNode->MetaData.SetMetaData(TEXT("Tooltip"), **TooltipPtr);
//                         UE_LOG(LogTemp, Display, TEXT("已设置蓝图 '%s' 函数 '%s' 的工具提示为：%s"), *Blueprint->GetName(), *FunctionName, **TooltipPtr);
//                     }
//                     bSuccess = true;
//                 }
//                 else if (debug)
//                 {
//                     UE_LOG(LogTemp, Display, TEXT("蓝图函数: %s"), *FunctionName);
//                 }
//             }
//         }
//     }

//     if (debug && !bSuccess)
//     {
//         UE_LOG(LogTemp, Warning, TEXT("设置失败，在 '%s' 中未找到匹配的属性或函数"), *BlueprintObject->GetName());
//     }
//     if (bSuccess)
//     {
//         FKismetEditorUtilities::CompileBlueprint(Blueprint, save ? EBlueprintCompileOptions::None : EBlueprintCompileOptions::SkipSave);
//     }

//     return bSuccess;
// }
