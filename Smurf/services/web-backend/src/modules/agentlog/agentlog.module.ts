import { Module } from '@nestjs/common';
import { AgentlogController } from './agentlog.controller';

@Module({
  controllers: [AgentlogController],
})
export class AgentlogModule {}
