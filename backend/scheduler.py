def generate_schedule(workers):

    schedule = []

    for worker in workers:
        schedule.append({
            "name": worker[1],
            "hours": worker[2]
        })

    return schedule