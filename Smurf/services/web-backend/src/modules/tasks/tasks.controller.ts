import { Controller, Get, Patch, Param, Query, NotFoundException, Body } from '@nestjs/common';
import { DbService } from '../db/db.service';
import { KafkaService } from '../kafka/kafka.service';
import { EventsGateway } from '../websocket/events.gateway';

@Controller('api/v1/tasks')
export class TasksController {
  constructor(
    private readonly dbService: DbService,
    private readonly kafkaService: KafkaService,
    private readonly eventsGateway: EventsGateway,
  ) {}

  @Get()
  getTasks(@Query('status') status?: string, @Query('limit') limit: number = 50) {
    const tasks = this.dbService.getTasks(status, Number(limit) || 50);
    return {
      total: tasks.length,
      status_filter: status || 'ALL',
      data: tasks,
    };
  }

  @Get(':id')
  getTaskById(@Param('id') id: string) {
    const task = this.dbService.getTaskById(id);
    if (!task) {
      throw new NotFoundException(`Inspection Task with ID ${id} not found`);
    }
    return task;
  }

  @Patch(':id/verify')
  async verifyTask(@Param('id') id: string, @Body() body?: any) {
    const task: any = this.dbService.getTaskById(id);
    if (!task) {
      throw new NotFoundException(`Inspection Task with ID ${id} not found`);
    }

    const updated = this.dbService.updateTaskStatus(id, 'CLOSED', 'VERIFIED');
    const eventPayload = {
      action: 'VERIFY_INSPECTION',
      task_id: id,
      device_id: task.device_id,
      engineer: body?.engineer || 'Field Engineer',
      timestamp: Date.now(),
      status: 'CLOSED',
      verification_status: 'VERIFIED',
    };

    await this.kafkaService.publishAction(
      process.env.TOPIC_INSPECTION_TASKS || 'topic_inspection_tasks',
      id,
      eventPayload,
    );
    this.eventsGateway.broadcast('TASK_STATUS_CHANGED', eventPayload);

    return {
      message: `Inspection Task ${id} for device ${task.device_id} is VERIFIED and CLOSED.`,
      ...updated,
    };
  }
}
