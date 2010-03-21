# django imports
from django.contrib.auth.models import Group
from django.contrib.contenttypes.models import ContentType

# workflows imports
from workflows.models import StateInheritanceBlock
from workflows.models import StateObjectRelation
from workflows.models import StatePermissionRelation
from workflows.models import Transition
from workflows.models import Workflow
from workflows.models import WorkflowModelRelation
from workflows.models import WorkflowObjectRelation
from workflows.models import WorkflowPermissionRelation

# permissions imports
import permissions.utils

def get_objects_for_workflow(workflow):
    """Returns all objects which have passed workflow.
    """
    if not isinstance(workflow, Workflow):
        try:
            workflow = Workflow.objects.get(name=workflow)
        except Workflow.DoesNotExist:
            return []

    for wmr in WorkflowModelRelation.objects.filter(workflow=workflow):
        ctype = wmr.content_type
        return ctype.model_class().objects.all()

def remove_workflow(ctype_or_obj):
    """Removes the workflow from the passed content type or object. After this
    function has been called the content type or object has no workflow
    anymore.

    If ctype_or_obj is an object the workflow is removed from the object not
    from the belonging conten type.

    If ctype_or_obj is an content type the workflow is removed from the
    content type not from instances of the content type (if they have an own
    workflow)

    ctype_or_obj
        The content type or the object to which the passed workflow should be
        set. Can be either a ContentType instance or any LFC Django model
        instance.
    """
    if isinstance(ctype_or_obj, ContentType):
        remove_workflow_from_model(ctype_or_obj)
    else:
        remove_workflow_from_obj(ctype_or_obj)

def remove_workflow_from_model(ctype):
    """Removes the workflow from passed content type. After this function has
    been called the content type has no workflow anymore (the instances might
    have own ones).

    ctype
        The content type from which the passed workflow should be removed.
        Must be a ContentType instance.
    """
    try:
        wmr = WorkflowModelRelation.objects.get(content_type=ctype)
    except WorkflowModelRelation.DoesNotExist:
        pass
    else:
        wmr.delete()

def remove_workflow_from_obj(obj):
    """Removes the workflow from the passed object. After this function has
    been called the object has no *own* workflow anymore (it might have one
    via its content type).

    obj
        The object from which the passed workflow should be set. Must be a
        Django Model instance.
    """
    try:
        wor = WorkflowObjectRelation.objects.get(content_type=ctype_or_obj)
    except WorkflowObjectRelation.DoesNotExist:
        pass
    else:
        wor.delete()

def set_workflow(ctype_or_obj, workflow):
    """Sets the workflow for passed content type or object. See the specific
    methods for more information.

    **Parameters:**

    workflow
        The workflow which should be set to the object or model.
    ctype_or_obj
        The content type or the object to which the passed workflow should be
        set. Can be either a ContentType instance or any Django model
        instance.
    """
    if isinstance(ctype_or_obj, ContentType):
        return set_workflow_for_model(ctype_or_obj, workflow)
    else:
        return set_workflow_for_object(ctype_or_obj, workflow)

def set_workflow_for_object(obj, workflow):
    """Sets the passed workflow to the passed object.

    If the object has already the given workflow nothing happens. Otherwise
    the object gets the passed workflow and the state is set to the workflow's
    initial state.

    **Parameters:**

    workflow
        The workflow which should be set to the object.
    obj
        The object which gets the passed workflow.
    """
    if isinstance(workflow, Workflow) == False:
        try:
            workflow = Workflow.objects.get(name=workflow)
        except Workflow.DoesNotExist:
            return False

    ctype = ContentType.objects.get_for_model(obj)
    try:
        wor = WorkflowObjectRelation.objects.get(content_type=ctype, content_id=obj.id)
    except WorkflowObjectRelation.DoesNotExist:
        WorkflowObjectRelation.objects.create(content = obj, workflow=workflow)
        set_state(obj, workflow.initial_state)
    else:
        if wor.workflow != workflow:
            wor.workflow = workflow
            wor.save()
            set_state(obj, workflow.initial_state)

def set_workflow_for_model(ctype, workflow):
    """Sets the passed workflow to the passed content type. If the content
    type has already an assigned workflow the workflow is overwritten.

    The objects which had the old workflow must updated explicitely.

    **Parameters:**

    workflow
        The workflow which should be set to passend content type. Must be a
        Workflow instance.
    ctype
        The content type to which the passed workflow should be assigned. Can
        be any Django model instance
    """
    if isinstance(workflow, Workflow) == False:
        try:
            workflow = Workflow.objects.get(name=workflow)
        except Workflow.DoesNotExist:
            return False
    try:
        wor = WorkflowModelRelation.objects.get(content_type=ctype)
    except WorkflowModelRelation.DoesNotExist:
        WorkflowModelRelation.objects.create(content_type=ctype, workflow=workflow)
    else:
        wor.workflow = workflow
        wor.save()

def get_workflow(obj):
    """Returns the workflow for the passed object. It takes it either from
    the passed object or - if the object doesn't have a workflow - from the
    passed object's ContentType.

    **Parameters:**

    object
        The object for which the workflow should be returend. Can be any
        Django model instance.
    """
    workflow = get_workflow_for_obj(obj)
    if workflow is not None:
        return workflow

    ctype = ContentType.objects.get_for_model(obj)
    return get_workflow_for_model(ctype)

def get_workflow_for_obj(obj):
    """Returns the workflow for the passed object.

    **Parameters:**

    obj
        The object for which the workflow should be returned. Can be any
        Django model instance.
    """
    try:
        wor = WorkflowObjectRelation.objects.get()
    except WorkflowObjectRelation.DoesNotExist:
        return None
    else:
        return wor.workflow

def get_workflow_for_model(ctype):
    """Returns the workflow for the passed model.

    **Parameters:**

    ctype
        The content type for which the workflow should be returned. Must be
        a Django ContentType instance.
    """
    try:
        wor = WorkflowModelRelation.objects.get(content_type=ctype)
    except WorkflowModelRelation.DoesNotExist:
        return None
    else:
        return wor.workflow

def get_state(obj):
    """Returns the current workflow state for the passed object.

    **Parameters:**

    obj
        The object for which the workflow state should be returned. Can be any
        Django model instance.
    """
    ctype = ContentType.objects.get_for_model(obj)
    try:
        sor = StateObjectRelation.objects.get(content_type=ctype, content_id=obj.id)
    except StateObjectRelation.DoesNotExist:
        return None
    else:
        return sor.state

def do_transition(obj, transition, user):
    """Processes the passed transition to the passed object (if allowed).
    """
    if not isinstance(transition, Transition):
        try:
            transition = Transition.objects.get(name=transition)
        except Transition.DoesNotExist:
            return False

    transitions = get_allowed_transitions(obj, user)
    if transition in transitions:
        set_state(obj, transition.destination)
        return True
    else:
        return False

def set_state(obj, state):
    """Sets the current state for the passed object and updates the
    permissions for the object.

    **Parameters:**

    obj
        The object for which the workflow state should be set. Can be any
        Django model instance.
    state
        The state which should be set to the passed object.
    """
    ctype = ContentType.objects.get_for_model(obj)
    try:
        sor = StateObjectRelation.objects.get(content_type=ctype, content_id=obj.id)
    except StateObjectRelation.DoesNotExist:
        sor = StateObjectRelation.objects.create(content=obj, state=state)
    else:
        sor.state = state
        sor.save()
    update_permissions(obj)

def set_initial_state(obj):
    """Sets the initial state to the passed object.
    """
    wf = get_workflow(obj)
    if wf is not None:
        set_state(obj, wf.initial_state)

def get_allowed_transitions(obj, user):
    """Returns all allowed transitions for passed object and user. Takes the
    current state of the object into account.

    **Parameters:**

    obj
        The object for which the transitions should be returned.
    user
        The user for which the transitions are allowed.
    """
    state = get_state(obj)

    transitions = []
    for transition in state.transitions.all():
        transitions.append(transition)

    return transitions

def update_permissions(obj):
    """Updates the permission of the object according to the object's current
       workflow state.
    """
    workflow = get_workflow(obj)
    state = get_state(obj)

    # Remove all permissions for the workflow
    for group in Group.objects.all():
        for wpr in WorkflowPermissionRelation.objects.filter(workflow=workflow):
            permissions.utils.remove_permission(obj, wpr.permission, group)

    # Grant permission for the state
    for spr in StatePermissionRelation.objects.filter(state=state):
        permissions.utils.grant_permission(obj, spr.permission, spr.group)

    # Remove all inheritance blocks from the object
    for wpr in WorkflowPermissionRelation.objects.filter(workflow=workflow):
        permissions.utils.remove_inheritance_block(obj, wpr.permission)

    # Add inheritance blocks of this state to the object
    for sib in StateInheritanceBlock.objects.filter(state=state):
        permissions.utils.add_inheritance_block(obj, sib.permission)