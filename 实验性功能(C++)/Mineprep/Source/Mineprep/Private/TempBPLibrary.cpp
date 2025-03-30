// // Copyright Epic Games, Inc. All Rights Reserved.

// #include "TempBPLibrary.h"
// #include "Mineprep.h"
// #include "MovieScene/Parameters/MovieSceneNiagaraParameterTrack.h"
// #include "NiagaraTypes.h"




// float4 color;

// // 获取全局重力
// RT.LoadRenderTargetValue(0, 0, 0, color);
// Gravity = float3(color.x, color.y, color.z);

// // 获取力场数组长度
// int forcesCount;
// RT.LoadRenderTargetValue(0, 1, 0, color);
// forcesCount = int(color.x);

// OutForce = PhysicsForce;

// // 遍历所有力场
// for (int i = 0; i < forcesCount; i++)
// {
//     // 获取当前力场位置
//     RT.LoadRenderTargetValue(1, i, 0, color);
//     float3 RadialForcePosition = float3(color.x, color.y, color.z);

//     // 获取当前力场参数
//     float4 RadialForceParams;
//     RT.LoadRenderTargetValue(2, i, 0, RadialForceParams);

//     // 解析力场参数
//     float strength = RadialForceParams.x;
//     float radius = RadialForceParams.y;
//     float falloff = RadialForceParams.z;

//     // 计算粒子到力场的向量
//     float3 directionToField = Position - RadialForcePosition;

//     // 计算距离
//     float distance = length(directionToField);

//     // 仅在影响半径内计算力
//     if (distance <= radius)
//     {
//         // 归一化方向向量
//         float3 normalizedDirection = distance > 0.0001f ? directionToField / distance : float3(0, 0, 0);

//         // 计算基于距离的力强度衰减
//         float distanceRatio = clamp(distance / radius, 0.0f, 1.0f);
//         float forceFactor = 1.0f - pow(distanceRatio, 1/falloff);

//         // 如果强度为正，则是斥力；为负，则是引力
//         float3 forceVector = normalizedDirection * strength * forceFactor * weight;

//         // 累加到粒子的物理力上
//         OutForce += forceVector;
//     }
// }
// debugForce = (OutForce-PhysicsForce)/100;