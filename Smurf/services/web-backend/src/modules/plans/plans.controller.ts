import { Controller, Get, Patch, Param, Query, NotFoundException, Body } from '@nestjs/common';
import { DbService } from '../db/db.service';
import { KafkaService } from '../kafka/kafka.service';
import { EventsGateway } from '../websocket/events.gateway';

@Controller('api/v1/plans')
export class PlansController {
  constructor(
    private readonly dbService: DbService,
    private readonly kafkaService: KafkaService,
    private readonly eventsGateway: EventsGateway,
  ) {}

  @Get()
  getPlans(@Query('status') status?: string, @Query('limit') limit: number = 50) {
    const plans = this.dbService.getPlans(status, Number(limit) || 50);
    return {
      total: plans.length,
      status_filter: status || 'ALL',
      data: plans,
    };
  }

  @Get(':id')
  getPlanById(@Param('id') id: string) {
    const plan = this.dbService.getPlanById(id);
    if (!plan) {
      throw new NotFoundException(`Irrigation Plan with ID ${id} not found`);
    }
    return plan;
  }

  @Patch(':id/approve')
  async approvePlan(@Param('id') id: string, @Body() body?: any) {
    const plan = this.dbService.getPlanById(id);
    if (!plan) {
      throw new NotFoundException(`Irrigation Plan with ID ${id} not found`);
    }

    const updated = this.dbService.updatePlanStatus(id, 'APPROVED');
    const eventPayload = {
      action: 'APPROVE_PLAN',
      plan_id: id,
      operator: body?.operator || 'Farm Manager',
      timestamp: Date.now(),
      status: 'APPROVED',
    };

    await this.kafkaService.publishAction(process.env.TOPIC_IRRIGATION_PLANS || 'topic_irrigation_plans', eventPayload);
    this.eventsGateway.broadcast('PLAN_STATUS_CHANGED', eventPayload);

    return {
      message: `Plan ${id} successfully APPROVED. Ready for execution.`,
      ...updated,
    };
  }

  @Patch(':id/reject')
  async rejectPlan(@Param('id') id: string, @Body() body?: any) {
    const plan = this.dbService.getPlanById(id);
    if (!plan) {
      throw new NotFoundException(`Irrigation Plan with ID ${id} not found`);
    }

    const updated = this.dbService.updatePlanStatus(id, 'REJECTED');
    const eventPayload = {
      action: 'REJECT_PLAN',
      plan_id: id,
      reason: body?.reason || 'Rejected by Manager',
      operator: body?.operator || 'Farm Manager',
      timestamp: Date.now(),
      status: 'REJECTED',
    };

    await this.kafkaService.publishAction(process.env.TOPIC_IRRIGATION_PLANS || 'topic_irrigation_plans', eventPayload);
    this.eventsGateway.broadcast('PLAN_STATUS_CHANGED', eventPayload);

    return {
      message: `Plan ${id} REJECTED.`,
      ...updated,
    };
  }
}
