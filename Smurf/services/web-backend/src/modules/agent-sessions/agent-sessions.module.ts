import { Module } from '@nestjs/common';
import { AgentSessionsController } from './agent-sessions.controller';
import { KafkaModule } from '../kafka/kafka.module';

@Module({
  imports: [KafkaModule],
  controllers: [AgentSessionsController],
})
export class AgentSessionsModule {}
