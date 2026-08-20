import manualCases from "./manualCases.json";
import type { WorkflowStatus } from "../types/workflow";

export type ManualCase = {
  id: string;
  prompt: string;
  session_id?: string;
  expected_status: WorkflowStatus;
  expected_order_id?: string;
  expect_hitl: boolean;
  decision?: "approve" | "reject";
  required_events?: string[];
  forbidden_events?: string[];
};

export const MANUAL_CASES = manualCases as ManualCase[];
