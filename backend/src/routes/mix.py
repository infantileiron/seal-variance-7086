import json
from fastapi import APIRouter,Depends
from fastapi.responses import Response
from src.config.database import get_db
from src.utils.security import current_user,editor
from src.schemas.business import MixBoundInput
from src.services import mix
from src.controllers.business import serialize,serialize_many
router=APIRouter()
@router.get('/assessments/{aid}/mix')
def panel(aid:int,db=Depends(get_db),user=Depends(current_user)):
    data=mix.panel(db,aid)
    return {'bounds':serialize_many(data['bounds']),'studies':serialize_many(data['studies']),'publications':serialize_many(data['publications']),'known_lots':data['known_lots'],'current_fingerprint':data['current_fingerprint']}
@router.put('/assessments/{aid}/mix-bounds')
def save_bound(aid:int,data:MixBoundInput,db=Depends(get_db),user=Depends(editor)):return serialize(mix.save_bound(db,aid,data,user))
@router.post('/assessments/{aid}/mix-studies',status_code=202)
def create_study(aid:int,db=Depends(get_db),user=Depends(editor)):return serialize(mix.create_study(db,aid,user))
@router.post('/assessments/{aid}/mix-studies/{sid}/publish')
def publish(aid:int,sid:int,db=Depends(get_db),user=Depends(editor)):return serialize(mix.publish(db,aid,sid,user))
@router.get('/assessments/{aid}/mix-publications/{pid}/export')
def export(aid:int,pid:int,db=Depends(get_db),user=Depends(current_user)):
    item=mix.get_publication(db,aid,pid)
    return Response(json.dumps(item.report,ensure_ascii=False,indent=2),media_type='application/json',headers={'Content-Disposition':f'attachment; filename="mix-report-v{item.version}-a{aid}.json"'})
