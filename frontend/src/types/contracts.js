/** @typedef {{id:number,code:string,name:string,temperature:number,dwell:number,pressure:number,note:string}} Process */
/** @typedef {{id:number,code:string,process_id:number,lot:string,force:number,flagged:boolean,note:string}} Sample */
/** @typedef {{id:number,title:string,status:'queued'|'running'|'completed'|'failed',snapshot:object,result:object|null,recommendation:string,approved:boolean}} Assessment */
/** @typedef {{id:number,assessment_id:number,lot:string,lower:number,upper:number,updated_by:string,updated_at:string}} MixBound */
/** @typedef {{id:number,assessment_id:number,status:'queued'|'running'|'completed'|'failed',input_fingerprint:string,result:object|null,error:string,created_by:string,created_at:string,finished_at:string}} MixStudy */
/** @typedef {{id:number,assessment_id:number,study_id:number,version:number,report:object,fingerprint:string,stale:boolean,published_by:string,published_at:string}} MixPublication */
export const contractsVersion='seal-variance-2';
