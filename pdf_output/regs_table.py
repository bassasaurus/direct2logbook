def regs_table():
    regs_objects = Regs.objects.filter(user=user)

    regs_data = []
    for regs in regs_objects:
        row = [str(regs.reg_type), str(regs.pilot_in_command), str(regs.second_in_command)]

        regs_data.append(row)

    regs_header = ["FAR", "PIC", "SIC"]

    regs_data.insert(0, regs_header)

    return regs_data
