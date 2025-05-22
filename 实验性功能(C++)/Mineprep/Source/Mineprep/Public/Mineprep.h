// Copyright Epic Games, Inc. All Rights Reserved.

#pragma once

#include "Modules/ModuleManager.h"
#include "Delegates/Delegate.h" // 添加委托头文件

class FMineprepModule : public IModuleInterface
{
public:
	/** IModuleInterface implementation */
	virtual void StartupModule() override;
	virtual void ShutdownModule() override;
	
private:
	// 引擎初始化后的委托句柄
	FDelegateHandle PostEngineInitDelegateHandle;
};
