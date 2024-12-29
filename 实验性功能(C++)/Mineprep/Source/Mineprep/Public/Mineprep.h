// Copyright Epic Games, Inc. All Rights Reserved.

#pragma once

#include "Modules/ModuleManager.h"

class FMineprepModule : public IModuleInterface
{
public:

	/** IModuleInterface implementation */
	virtual void StartupModule() override;
	virtual void ShutdownModule() override;

private:
	void ExecuteKey0Command();
	void ExecuteKey1Command();
	void ExecuteKey2Command();
	void ExecuteKey3Command();
	void ExecuteKey4Command();
	void ExecuteKey5Command();
	void ExecuteKey6Command();
	void ExecuteKey7Command();
	void ExecuteKey8Command();
	void ExecuteKey9Command();
	void ExecuteBlueprintEvent(FName EventName);
};
