import hashlib,json
from datetime import datetime,timezone
from sqlalchemy import select
from fastapi import HTTPException
import redis
from src.models.entities import Assessment,MixBound,MixStudy,MixPublication,Sample
from src.services.assessments import queue
from src.services.mixstats import analyze
def _now():return datetime.now(timezone.utc).isoformat()
def get_assessment(db,assessment_id):
    item=db.get(Assessment,assessment_id)
    if not item:raise HTTPException(404,'评议任务不存在')
    return item
def fingerprint(assessment,samples,bounds):
    payload={'assessment':assessment.id,'processes':sorted(g['id'] for g in assessment.snapshot['groups']),'samples':[[s.code,s.process_id,s.lot,s.force] for s in samples],'bounds':[[b.lot,b.lower,b.upper] for b in bounds]}
    return hashlib.sha256(json.dumps(payload,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
def current_inputs(db,assessment):
    pids=[g['id'] for g in assessment.snapshot['groups']]
    samples=db.scalars(select(Sample).where(Sample.process_id.in_(pids)).order_by(Sample.code)).all()
    bounds=db.scalars(select(MixBound).where(MixBound.assessment_id==assessment.id).order_by(MixBound.lot)).all()
    return samples,bounds
def panel(db,assessment_id):
    assessment=get_assessment(db,assessment_id)
    samples,bounds=current_inputs(db,assessment)
    studies=db.scalars(select(MixStudy).where(MixStudy.assessment_id==assessment_id).order_by(MixStudy.id.desc())).all()
    publications=db.scalars(select(MixPublication).where(MixPublication.assessment_id==assessment_id).order_by(MixPublication.version.desc())).all()
    return {'bounds':bounds,'studies':studies,'publications':publications,'known_lots':sorted({s.lot for s in samples}),'current_fingerprint':fingerprint(assessment,samples,bounds)}
def save_bound(db,assessment_id,data,user):
    get_assessment(db,assessment_id)
    lot=data.lot.strip()
    if not lot:raise HTTPException(422,'批次号不能为空')
    if data.lower>data.upper:raise HTTPException(422,'占比下限不能高于上限')
    item=db.scalar(select(MixBound).where(MixBound.assessment_id==assessment_id,MixBound.lot==lot))
    if not item:
        if len(db.scalars(select(MixBound).where(MixBound.assessment_id==assessment_id)).all())>=50:raise HTTPException(422,'单个评议的配比批次不能超过50个')
        item=MixBound(assessment_id=assessment_id,lot=lot)
    item.lower=data.lower;item.upper=data.upper;item.updated_by=user.email;item.updated_at=_now()
    db.add(item);db.commit();db.refresh(item);return item
def create_study(db,assessment_id,user):
    assessment=get_assessment(db,assessment_id)
    if assessment.status!='completed':raise HTTPException(409,'单因素分析完成后才能发起配比敏感性计算')
    if len(db.scalars(select(MixStudy).where(MixStudy.status.in_(['queued','running']))).all())>=10:raise HTTPException(429,'待执行的配比计算过多，请稍后重试')
    item=MixStudy(assessment_id=assessment_id,status='queued',created_by=user.email,created_at=_now())
    db.add(item);db.commit();db.refresh(item)
    try:queue.lpush('seal:mix',item.id)
    except redis.RedisError:
        item.status='failed';item.error='队列不可用，请恢复后重新提交';db.commit();raise HTTPException(503,item.error)
    return item
def run_study(db,study):
    assessment=db.get(Assessment,study.assessment_id)
    samples,bounds=current_inputs(db,assessment)
    processes=[{'id':g['id'],'code':g['code'],'name':g['name']} for g in assessment.snapshot['groups']]
    study.result=analyze(processes,[{'process_id':s.process_id,'lot':s.lot,'force':s.force} for s in samples],[{'lot':b.lot,'lower':b.lower,'upper':b.upper} for b in bounds])
    study.input_fingerprint=fingerprint(assessment,samples,bounds)
    study.status='completed';study.finished_at=_now()
def get_publication(db,assessment_id,publication_id):
    item=db.get(MixPublication,publication_id)
    if not item or item.assessment_id!=assessment_id:raise HTTPException(404,'发布版本不存在')
    return item
def publish(db,assessment_id,study_id,user):
    assessment=get_assessment(db,assessment_id)
    study=db.get(MixStudy,study_id)
    if not study or study.assessment_id!=assessment_id:raise HTTPException(404,'配比计算任务不存在')
    if study.status!='completed':raise HTTPException(409,'计算未成功完成，不能发布')
    samples,bounds=current_inputs(db,assessment)
    fp=fingerprint(assessment,samples,bounds)
    latest=db.scalar(select(MixPublication).where(MixPublication.assessment_id==assessment_id).order_by(MixPublication.version.desc()).limit(1))
    if fp!=study.input_fingerprint:
        if latest and not latest.stale:latest.stale=True;db.commit()
        raise HTTPException(409,'样本或占比已修订，该结果无法用现行数据复算，不予发布；已保留旧版并标注时效，请重新计算')
    existing=db.scalar(select(MixPublication).where(MixPublication.assessment_id==assessment_id,MixPublication.study_id==study_id))
    if existing:return existing
    if latest and latest.fingerprint==fp:return latest
    version=latest.version+1 if latest else 1
    now=_now()
    report={'version':version,'assessment':{'id':assessment.id,'title':assessment.title,'lot':assessment.lot},'study_id':study.id,'fingerprint':fp,'conclusion':study.result.get('conclusion'),'complete':study.result.get('complete'),'no_conclusion_reason':study.result.get('no_conclusion_reason'),'pairs':study.result.get('pairs'),'lots':study.result.get('lots'),'ignored_lots':study.result.get('ignored_lots',[]),'method':study.result.get('method'),'computed_at':study.finished_at,'published_at':now,'published_by':user.email}
    item=MixPublication(assessment_id=assessment_id,study_id=study.id,version=version,report=report,fingerprint=fp,stale=False,published_by=user.email,published_at=now)
    db.add(item);db.commit();db.refresh(item);return item
