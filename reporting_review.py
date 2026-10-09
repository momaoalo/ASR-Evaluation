"""Explicit review decisions and reference corrections; original runs are immutable."""
import copy
from storage import read_json, write_json, load_result, save_result, digest, new_id, now, valid_id
from evaluation.evaluator import evaluate_transcription
from evaluation.profiles import get_cleaning_profile


def load_reviews(settings):
    directory = settings.data / 'reviews'
    out = {}
    for path in directory.glob('*/*.json'):
        try:
            value=read_json(path)
            if isinstance(value, dict) and value.get('status') in ('confirmed','excluded','unreviewed'):
                out[path.parent.name+'/'+path.stem]=value
        except (OSError,ValueError):
            out.setdefault('_warnings', []).append({'run_id':path.parent.name,'case_id':path.stem,'message':'A saved review decision could not be read. Check this case before relying on aggregate inclusion.'})
    return out


def save_review(settings, run_id, case_id, payload):
    case=load_result(settings,valid_id(run_id),valid_id(case_id))
    status=payload.get('status')
    if status not in ('confirmed','excluded','unreviewed'):
        raise ValueError('Choose confirmed, excluded or unreviewed.')
    note=payload.get('note','')
    if not isinstance(note,str) or len(note)>1000:
        raise ValueError('The review note is limited to 1000 characters.')
    value={'status':status,'note':note,'updated_at':now(),'reference_hash':case.get('reference_hash') or digest(case.get('reference',''))}
    write_json(settings.data/'reviews'/run_id/(case_id+'.json'),value)
    return value


def rescore_reference(settings, run_id, case_id, payload):
    """Create a new result using existing model text. Never send audio or a hint."""
    if payload.get('confirmed') is not True:
        raise ValueError('Confirm you reviewed this reference against the exact audio.')
    reference=payload.get('reference')
    if not isinstance(reference,str) or not reference.strip() or len(reference)>settings.max_text_chars:
        raise ValueError('Provide a non-empty reference within the text limit.')
    original=load_result(settings,valid_id(run_id),valid_id(case_id))
    if not any(m.get('status')=='success' for m in original.get('models',[])):
        raise ValueError('No saved successful model text is available for re-scoring.')
    result=copy.deepcopy(original)
    new_run=new_id('reviewed')
    result.update(run_id=new_run,created_at=now(),reference=reference,reference_hash=digest(reference),
                  rescored_from={'run_id':run_id,'case_id':case_id},
                  reference_review={'confirmed':True,'at':now(),'previous_reference_hash':original.get('reference_hash')})
    profile=original.get('profile') or get_cleaning_profile()
    for model in result['models']:
        if model.get('status')=='success':
            speech=model.get('speech_text')
            if not isinstance(speech,str): speech=model.get('raw_text')
            if not isinstance(speech,str): raise ValueError('Original transcript text is unavailable; no score was invented.')
            model['evaluation']=evaluate_transcription(reference,speech,profile)
    result['trace']=list(result.get('trace') or [])+[{'stage':'Reference reviewed; re-scored stored texts without ASR requests','at':now()}]
    save_result(settings,result)
    job={'run_id':new_run,'job_id':new_run,'created_at':now(),'updated_at':now(),
         'name':result.get('title','Evaluation')+' · reviewed reference','status':result['status'],
         'mode':'rescore','profile':profile,'score_view':'normalized','models':[m['key'] for m in result['models']],
         'completed':1,'total':1,'case_headers':[{'case_id':case_id,'title':result.get('title',case_id)}]}
    write_json(settings.data/'jobs'/(new_run+'.json'),job)
    save_review(settings,run_id,case_id,{'status':'excluded','note':'Superseded by a user-reviewed reference in '+new_run+'. Original scores retained.'})
    save_review(settings,new_run,case_id,{'status':'confirmed','note':'Reviewed reference; new score computed from saved text.'})
    return job
