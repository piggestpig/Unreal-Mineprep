#include "MovieGraphFilmicHDRRenderPassNode.h"

#include "MineprepDisplayHDRRenderTarget.h"
#include "EdGraph/EdGraphNode.h"
#include "Graph/MovieGraphConfig.h"
#include "Graph/MovieGraphPipeline.h"
#include "Graph/Renderers/MovieGraphDeferredPass.h"
#include "RenderingThread.h"

namespace
{
struct FFilmicTarget
{
    const FRenderTarget* Original;
    float Peak;
    float White;
    bool bPQ;
    TSharedPtr<FMineprepDisplayHDRRenderTarget> Proxy;
};

struct FMovieGraphFilmicHDRPass : UE::MovieGraph::Rendering::FMovieGraphDeferredPass
{
    mutable TArray<FFilmicTarget> Targets;

    virtual UMovieGraphImagePassBaseNode* GetParentNode(UMovieGraphEvaluatedConfig* Config) const override
    {
        return Config->GetSettingForBranch<UMovieGraphFilmicHDRRenderPassNode>(GetBranchName(), true, true);
    }

    virtual void ApplyMovieGraphOverridesToViewFamily(
        TSharedRef<FSceneViewFamilyContext> Family,
        const UE::MovieGraph::Rendering::FViewFamilyInitData& Init) const override
    {
        FMovieGraphDeferredPass::ApplyMovieGraphOverridesToViewFamily(Family, Init);
        const auto* Node = Cast<UMovieGraphFilmicHDRRenderPassNode>(GetParentNode(Init.TimeData.EvaluatedConfig));
        if (!Node || !Family->RenderTarget)
        {
            return;
        }
        if (!FMath::IsFinite(Node->PeakNits) || Node->PeakNits <= 100.f || Node->PeakNits > 10000.f ||
            !FMath::IsFinite(Node->PaperWhiteNits) || Node->PaperWhiteNits <= 0.f || Node->PaperWhiteNits > Node->PeakNits)
        {
            UE_LOG(LogTemp, Error, TEXT("Filmic HDR requires 100 < peak <= 10000 and 0 < paper white <= peak."));
            if (const auto Renderer = GetRenderer().Get())
            {
                Renderer->GetOwningGraph()->RequestShutdown(true);
            }
            return;
        }
        const FRenderTarget* Original = Family->RenderTarget;
        const FFilmicTarget* Target = Targets.FindByPredicate([&](const FFilmicTarget& Entry)
        {
            return Entry.Original == Original && Entry.Peak == Node->PeakNits &&
                Entry.White == Node->PaperWhiteNits && Entry.bPQ == Node->bOutputPQ;
        });
        if (!Target)
        {
            Target = &Targets.Add_GetRef({Original, Node->PeakNits, Node->PaperWhiteNits, Node->bOutputPQ,
                MakeShared<FMineprepDisplayHDRRenderTarget>(*Original, Node->PeakNits, Node->PaperWhiteNits, Node->bOutputPQ)});
        }
        Family->RenderTarget = Target->Proxy.Get();
        Family->SceneCaptureSource = SCS_FinalColorLDR;
        Family->EngineShowFlags.SetToneCurve(true);
    }

    virtual void ApplyMovieGraphOverridesToSampleState(UE::MovieGraph::FMovieGraphSampleState& State) const override
    {
        State.SceneCaptureSource = SCS_FinalColorLDR;
        const auto* Node = Cast<UMovieGraphFilmicHDRRenderPassNode>(GetParentNode(State.TraversalContext.Time.EvaluatedConfig));
        if (Node)
        {
            State.AdditionalFileMetadata.Add(TEXT("mineprep/displayHDR/encoding"), Node->bOutputPQ ? TEXT("Rec.2020 D65; ST2084 PQ") : TEXT("linear scRGB; 1.0 = 80 cd/m2"));
            State.AdditionalFileMetadata.Add(TEXT("mineprep/displayHDR/peakNits"), FString::SanitizeFloat(Node->PeakNits));
            State.AdditionalFileMetadata.Add(TEXT("mineprep/displayHDR/paperWhiteNits"), FString::SanitizeFloat(Node->PaperWhiteNits));
        }
    }

    virtual void Teardown() override
    {
        // Keep every per-frame proxy alive until render-thread use has finished.
        if (!Targets.IsEmpty())
        {
            FlushRenderingCommands();
            Targets.Empty();
        }
        FMovieGraphDeferredPass::Teardown();
    }
};
}

UMovieGraphFilmicHDRRenderPassNode::UMovieGraphFilmicHDRRenderPassNode()
    : bOverride_bOutputPQ(true), bOverride_PeakNits(true), bOverride_PaperWhiteNits(true)
{
    bDisableToneCurve = false;
    bAllowOCIO = false;
}

void UMovieGraphFilmicHDRRenderPassNode::SetGraphNodePosition(UMovieGraphNode* Node, int32 X, int32 Y)
{
#if WITH_EDITOR
    if (Node)
    {
        Node->SetNodePosX(X);
        Node->SetNodePosY(Y);
        if (UEdGraphNode* EditorNode = Node->GraphNode)
        {
            EditorNode->NodePosX = X;
            EditorNode->NodePosY = Y;
        }
    }
#endif
}

TUniquePtr<UE::MovieGraph::Rendering::FMovieGraphImagePassBase> UMovieGraphFilmicHDRRenderPassNode::CreateInstance() const
{
    return MakeUnique<FMovieGraphFilmicHDRPass>();
}

#if WITH_EDITOR
FText UMovieGraphFilmicHDRRenderPassNode::GetNodeTitle(bool bGetDescriptive) const
{
    return NSLOCTEXT("Mineprep", "MovieGraphFilmicHDR", "Mineprep Filmic HDR Renderer");
}
#endif
