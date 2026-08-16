import { Module } from '@nestjs/common';
import { TasksController } from './tasks.controller';
import { KafkaModule } from '../kafka/kafka.module';
import { WebsocketModule } from '../websocket/websocket.module';

@Module({
  imports: [KafkaModule, WebsocketModule],
  controllers: [TasksController],
})
export class TasksModule {}
