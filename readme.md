# MQTT Topic Definition
1. {r_id}/available
2. req_path
    - r_id
    - path
3. {r_id}/task_path
4. amr_position



# Status
1. robots_registration

    - online: online
    - shutdown: normal shutdown
    - offline: abnormal lost

- Cleaning Process: if robot's offline for 60s, Traffic Manager
will assume robot was shutdown

- Init Process
- Clear Process
