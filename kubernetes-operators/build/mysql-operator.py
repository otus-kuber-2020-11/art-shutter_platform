#!/usr/bin/env python3

import kopf
import yaml
import kubernetes
import time
from jinja2 import Environment, FileSystemLoader

def render_template(filename, vars_dict):
    env = Environment(loader=FileSystemLoader('./templates'))
    template = env.get_template(filename)
    yaml_manifest = template.render(vars_dict)
    json_manifest = yaml.load(yaml_manifest, Loader=yaml.FullLoader)
    return json_manifest

def delete_success_jobs(mysql_instance_name):
    print("start deletion")
    api = kubernetes.client.BatchV1Api()
    jobs = api.list_namespaced_job('default')
    for job in jobs.items:
        jobname = job.metadata.name
        if (jobname == f"backup-{mysql_instance_name}-job") or \
                (jobname == f"restore-{mysql_instance_name}-job"):
            if job.status.succeeded == 1:
                print(f"Cleaning up Job: {jobname} Finished at: {job.status.completion_time}")
                api.delete_namespaced_job(
                    jobname,
                    'default',
                    propagation_policy='Background'
                )

def wait_until_job_end(jobname):
    api = kubernetes.client.BatchV1Api()
    job_finished = False
    jobs = api.list_namespaced_job('default')
    while (not job_finished) and \
            any(job.metadata.name == jobname for job in jobs.items):
        time.sleep(1)
        jobs = api.list_namespaced_job('default')
        for job in jobs.items:
            if job.metadata.name == jobname:
                print(f"job with { jobname } found, waiting on it to finish")
                if job.status.succeeded == 1:
                    print(f"job { jobname } has been successful")
                    job_finished = True

@kopf.on.create('otus.homework', 'v1', 'mysqls')
def mysql_on_create(body, spec, **kwargs):
    name = body['metadata']['name']
    image = body['spec']['image']
    password = body['spec']['password']
    database = body['spec']['database']
    storage_size = body['spec']['storage_size']

    persistent_volume = render_template(
        'mysql-pv.yaml.j2',
        {
            'name': name,
            'storage_size': storage_size
        }
    )
    persistent_volume_claim = render_template(
        'mysql-pvc.yaml.j2',
        {
            'name': name,
            'storage_size': storage_size
        }
    )
    service = render_template(
        'mysql-service.yaml.j2',
        {
            'name': name
        }
    )
    deployment = render_template(
        'mysql-deployment.yaml.j2',
        {
            'name': name,
            'image': image,
            'password': password,
            'database': database
        }
    )
    restore_job = render_template(
        'restore-job.yaml.j2',
        {
            'name': name,
            'image': image,
            'password': password,
            'database': database
        }
    )

    kopf.append_owner_reference(persistent_volume, owner=body)
    kopf.append_owner_reference(persistent_volume_claim, owner=body)
    kopf.append_owner_reference(service, owner=body)
    kopf.append_owner_reference(deployment, owner=body)

    api = kubernetes.client.CoreV1Api()
    try:
        api.create_persistent_volume(persistent_volume)
    except kubernetes.client.rest.ApiException as e:
            print("Exception on pv creation: %s\n" % e)
    api.create_namespaced_persistent_volume_claim('default', persistent_volume_claim)
    api.create_namespaced_service('default', service)

    api = kubernetes.client.AppsV1Api()
    api.create_namespaced_deployment('default', deployment)

    try:
        api = kubernetes.client.BatchV1Api()
        api.create_namespaced_job(
            'default',
            restore_job
        )
    except kubernetes.client.rest.ApiException as e:
        print("Exception on restore job: %s\n" % e)

    try:
        backup_pv = render_template(
            'backup-pv.yaml.j2',
            {
                'name': name
            }
        )
        api = kubernetes.client.CoreV1Api()
        api.create_persistent_volume(backup_pv)
    except kubernetes.client.rest.ApiException as e:
        print("Exception on backup pv: %s\n" % e)

    try:
        backup_pvc = render_template(
            'backup-pvc.yaml.j2',
            {
                'name': name
            }
        )
        api = kubernetes.client.CoreV1Api()
        api.create_namespaced_persistent_volume_claim('default', backup_pvc)
    except kubernetes.client.rest.ApiException as e:
        print("Exception on backup pvc: %s\n" % e)

@kopf.on.delete('otus.homework', 'v1', 'mysqls')
def delete_object_make_backup(body, **kwargs):
    name = body['metadata']['name']
    image = body['spec']['image']
    password = body['spec']['password']
    database = body['spec']['database']

    try:
        api = kubernetes.client.BatchV1Api()
        backup_job = render_template(
            'backup-job.yaml.j2',
            {
                'name': name,
                'image': image,
                'password': password,
                'database': database
            }
        )
        api.create_namespaced_job('default', backup_job)
    except kubernetes.client.rest.ApiException as e:
        print("Exception on backup job: %s\n" % e)

    wait_until_job_end(f"backup-{name}-job")
    delete_success_jobs(name)
    return {'message': "mysql and its children resources deleted"}
