import time,traceback,json
from pathlib import Path
from sqlalchemy import select
from src.config.database import SessionLocal
from src.models.entities import Assessment,MixStudy
from src.services.assessments import queue
from src.services.statistics import anova
from src.services.mix import run_study
with SessionLocal() as db:
    for task in db.scalars(select(Assessment).where(Assessment.status=='running')).all():task.status='queued'
    for task in db.scalars(select(MixStudy).where(MixStudy.status=='running')).all():task.status='queued'
    db.commit()
print('seal variance worker started',flush=True)
while True:
    Path('/tmp/worker-heartbeat').touch()
    try:
        queue.brpop(['seal:assessments','seal:mix'],timeout=2)
        with SessionLocal() as db:
            task=db.scalar(select(Assessment).where(Assessment.status=='queued').order_by(Assessment.id).with_for_update(skip_locked=True))
            if task:
                task.status='running';db.commit()
                try:
                    task.result=anova(task.snapshot);task.status='completed'
                    Path('/app/artifacts/'+str(task.id)+'.json').write_text(json.dumps(task.result,ensure_ascii=False))
                except Exception as e:task.error=str(e);task.status='failed'
                db.commit();print(f'assessment={task.id} status={task.status}',flush=True);continue
            study=db.scalar(select(MixStudy).where(MixStudy.status=='queued').order_by(MixStudy.id).with_for_update(skip_locked=True))
            if not study:continue
            study.status='running';db.commit()
            try:
                run_study(db,study)
                Path('/app/artifacts/mix-'+str(study.id)+'.json').write_text(json.dumps(study.result,ensure_ascii=False))
            except Exception as e:study.error=str(e);study.status='failed'
            db.commit();print(f'mix-study={study.id} status={study.status}',flush=True)
    except Exception:traceback.print_exc();time.sleep(2)
