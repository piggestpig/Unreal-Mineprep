#pragma once

#include "MoviePipelineFilmicHDRSetting.h"
#include "ColorManagement/ColorSpace.h"
#include "UnrealClient.h"

/** Borrow MRQ's render target and describe a fixed HDR mastering target, never a physical display. */
class FMineprepDisplayHDRRenderTarget final : public FRenderTarget
{
public:
    FMineprepDisplayHDRRenderTarget(const FRenderTarget& InTarget, float InPeakNits, float InPaperWhiteNits, bool bInOutputPQ)
        : Target(InTarget), PeakNits(InPeakNits), PaperWhiteNits(InPaperWhiteNits), bOutputPQ(bInOutputPQ)
    {
    }

    virtual const FTextureRHIRef& GetRenderTargetTexture() const override { return Target.GetRenderTargetTexture(); }
    virtual FRDGTextureRef GetRenderTargetTexture(FRDGBuilder& GraphBuilder) const override { return Target.GetRenderTargetTexture(GraphBuilder); }
    virtual FUnorderedAccessViewRHIRef GetRenderTargetUAV() const override { return Target.GetRenderTargetUAV(); }
    virtual const FTextureRHIRef& GetShaderResourceTexture() const override { return Target.GetShaderResourceTexture(); }
    virtual FIntPoint GetSizeXY() const override { return Target.GetSizeXY(); }
    virtual FRHIGPUMask GetGPUMask(FRHICommandListImmediate& RHICmdList) const override { return Target.GetGPUMask(RHICmdList); }

    virtual float GetDisplayGamma() const override { return 2.2f; }
    virtual EDisplayColorGamut GetDisplayColorGamut() const override { return bOutputPQ ? EDisplayColorGamut::Rec2020_D65 : EDisplayColorGamut::sRGB_D65; }
    virtual EDisplayOutputFormat GetDisplayOutputFormat() const override { return bOutputPQ ? EDisplayOutputFormat::HDR_ACES_1000nit_ST2084 : EDisplayOutputFormat::HDR_ACES_1000nit_ScRGB; }
    virtual bool GetSceneHDREnabled() const override { return true; }
    virtual float GetMinimumLuminanceInNits() const override { return 0.f; }
    virtual float GetMaximumLuminanceInNits() const override { return PeakNits; }
    virtual float GetMaximumFullFrameLuminanceInNits() const override { return PeakNits; }
    virtual float GetHDRPaperWhiteInNits() const override { return PaperWhiteNits; }
    virtual const UE::Color::FColorSpace& GetLimitingColorSpace() const override { return UE::Color::FColorSpace::GetRec2020(); }

private:
    const FRenderTarget& Target;
    const float PeakNits;
    const float PaperWhiteNits;
    const bool bOutputPQ;
};
