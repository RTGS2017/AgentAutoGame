#   AUTO-MAS: A Multi-Script, Multi-Config Management and Automation Software
#   Copyright © 2025-2026 AUTO-MAS Team
#
#   This file is part of AUTO-MAS.
#
#   AUTO-MAS is free software: you can redistribute it and/or modify
#   it under the terms of the GNU General Public License as published
#   by the Free Software Foundation, either version 3 of the License,
#   or (at your option) any later version.
#
#   AUTO-MAS is distributed in the hope that it will be useful,
#   but WITHOUT ANY WARRANTY; without even the implied warranty
#   of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See
#   the GNU General Public License for more details.
#
#   You should have received a copy of the GNU General Public License
#   along with AUTO-MAS. If not, see <https://www.gnu.org/licenses/>.

import calendar
from typing import Literal

from fastapi import APIRouter, Body
from pydantic import BaseModel, Field

from app.core import Config
from app.models.schema import OutBase

router = APIRouter(prefix="/api/agent", tags=["Agent 接口"])


class AgentScriptAddIn(BaseModel):
    type: Literal["MAA", "General"] = Field(
        default="General", description="脚本类型，General 可用于 MAA 之外的代理脚本"
    )
    name: str | None = Field(default=None, description="脚本名称")


class AgentScriptAddOut(OutBase):
    scriptId: str = Field(default="", description="脚本ID")
    scriptType: str = Field(default="", description="脚本配置类型")


class AgentPlanAddIn(BaseModel):
    name: str | None = Field(default=None, description="计划名称")
    mode: Literal["ALL", "Weekly"] = Field(default="ALL", description="计划模式")


class AgentPlanAddOut(OutBase):
    planId: str = Field(default="", description="计划ID")


class AgentPlanningCreateIn(BaseModel):
    queue_name: str = Field(default="新任务规划", description="队列名称")
    script_ids: list[str] = Field(
        default_factory=list, description="需要加入队列的脚本ID"
    )
    startup_enabled: bool = Field(default=False, description="是否开机启动")
    time_enabled: bool = Field(default=False, description="是否启用定时")
    days: list[
        Literal[
            "Monday",
            "Tuesday",
            "Wednesday",
            "Thursday",
            "Friday",
            "Saturday",
            "Sunday",
        ]
    ] = Field(default_factory=list, description="定时执行周期")
    time: str = Field(default="08:00", description="定时执行时间，格式 HH:MM")
    after_accomplish: Literal[
        "NoAction",
        "Shutdown",
        "ShutdownForce",
        "Reboot",
        "Hibernate",
        "Sleep",
        "KillSelf",
    ] = Field(default="NoAction", description="完成后动作")


class AgentPlanningCreateOut(OutBase):
    queueId: str = Field(default="", description="队列ID")
    queueItemIds: list[str] = Field(
        default_factory=list, description="创建的队列项ID列表"
    )
    timeSetId: str | None = Field(default=None, description="创建的定时项ID")


@router.post(
    "/script/add",
    tags=["Add"],
    summary="创建代理脚本（支持 General/MAA）",
    response_model=AgentScriptAddOut,
    status_code=200,
)
async def add_agent_script(script: AgentScriptAddIn = Body(...)) -> AgentScriptAddOut:
    try:
        uid, config = await Config.add_script(script.type)
        if script.name:
            await Config.update_script(str(uid), {"Info": {"Name": script.name}})
    except Exception as e:
        return AgentScriptAddOut(
            code=500,
            status="error",
            message=f"{type(e).__name__}: {str(e)}",
            scriptId="",
            scriptType="",
        )

    return AgentScriptAddOut(scriptId=str(uid), scriptType=type(config).__name__)


@router.post(
    "/plan/add",
    tags=["Add"],
    summary="创建任务规划计划表（MaaPlan）",
    response_model=AgentPlanAddOut,
    status_code=200,
)
async def add_agent_plan(plan: AgentPlanAddIn = Body(...)) -> AgentPlanAddOut:
    try:
        uid, _ = await Config.add_plan("MaaPlan")
        plan_data: dict[str, dict[str, str]] = {"Info": {"Mode": plan.mode}}
        if plan.name:
            plan_data["Info"]["Name"] = plan.name
        await Config.update_plan(str(uid), plan_data)
    except Exception as e:
        return AgentPlanAddOut(
            code=500,
            status="error",
            message=f"{type(e).__name__}: {str(e)}",
            planId="",
        )

    return AgentPlanAddOut(planId=str(uid))


@router.post(
    "/planning/create",
    tags=["Add"],
    summary="创建任务规划（队列+脚本项+可选定时）",
    response_model=AgentPlanningCreateOut,
    status_code=200,
)
async def create_agent_planning(
    planning: AgentPlanningCreateIn = Body(...),
) -> AgentPlanningCreateOut:
    queue_item_ids: list[str] = []
    time_set_id: str | None = None
    try:
        queue_uid, _ = await Config.add_queue()
        queue_id = str(queue_uid)

        await Config.update_queue(
            queue_id,
            {
                "Info": {
                    "Name": planning.queue_name,
                    "StartUpEnabled": planning.startup_enabled,
                    "TimeEnabled": planning.time_enabled,
                    "AfterAccomplish": planning.after_accomplish,
                }
            },
        )

        for script_id in planning.script_ids:
            queue_item_uid, _ = await Config.add_queue_item(queue_id)
            queue_item_id = str(queue_item_uid)
            await Config.update_queue_item(
                queue_id, queue_item_id, {"Info": {"ScriptId": script_id}}
            )
            queue_item_ids.append(queue_item_id)

        if planning.time_enabled:
            raw_days = planning.days or list(calendar.day_name)
            time_uid, _ = await Config.add_time_set(queue_id)
            time_set_id = str(time_uid)
            await Config.update_time_set(
                queue_id,
                time_set_id,
                {
                    "Info": {
                        "Enabled": True,
                        "Days": raw_days,
                        "Time": planning.time,
                    }
                },
            )
    except Exception as e:
        return AgentPlanningCreateOut(
            code=500,
            status="error",
            message=f"{type(e).__name__}: {str(e)}",
            queueId="",
            queueItemIds=queue_item_ids,
            timeSetId=time_set_id,
        )

    return AgentPlanningCreateOut(
        queueId=queue_id, queueItemIds=queue_item_ids, timeSetId=time_set_id
    )
