export type Session={session_id:string;source_path:string;state:string;active_round_id:string;active_round_number:number;updated_at:string;tasks_total:number;task_decisions_completed:number;unattributed_count:number};
export type Task={task_id:string;instruction:string;annotation_source:{adapter:string};locator:{exact_quote:string;prefix:string;suffix:string;locator_status:string;start_line:number|null;end_line:number|null};human_status:string};
export type ReceiptTask={task_id:string;outcome:string;summary:string;claimed_changes:{path:string;start_line:number;end_line:number}[];notes:string|null};
export type Association={task_id:string;confidence:"certain"|"likely"|"weak";methods:string[];reasons:string[]};
export type Hunk={hunk_id:string;old_start:number;new_start:number;before:string;after:string;associated_tasks:Association[];unattributed:boolean};
export type Check={rule_id:string;subject_type:string;subject_id:string;status:"pass"|"warning"|"fail"|"uncertain";message:string};
export type Decision={decision_id:string;subject_type:"task"|"hunk";subject_id:string;decision:string;reason:string};
export type Detail={session:Session;tasks:{tasks:Task[]}|null;receipt:{tasks:ReceiptTask[]}|null;evidence:{checks:Check[];hunks:Hunk[]}|null;decisions:{decisions:Decision[]};legal_actions:string[]};
