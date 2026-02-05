# Tasks

In files/doc_figure_sources. 
I want to set up customizable task object architecture which shall be serializable and extendable. 
The tasks should be serialized to the frontend which shall be able to display the tasks and their custom parameters.
The task objects can be referenced in the report using the task name and its property fields.

The `base_tasks.py` whould define a base scaffold for defining tasks and task objects using pydantic objects. 
These objects should be easily extendable and serializable.

The base task object shall contain fields such as

- "name": Name of the task
- "id": Unique identifier for the task
- "depends_on": List of task names that this task depends on
- "output": Task product. Can refer to a specific file or folder or a regex expression folder/**/*.py. Will be used to determine if the task needs to be rerun  

The `tasks/tasks.py` defines specific tasks inheriting on the base tasks. Below are the tasks I want to define:

1. `Simulate`:
    - `name`: Name of the simulation task
    - `output`: Output file or folder for the simulation results
    - `ca`: Refers to the `CodeAsterResults` task object
    - `cx`: Refers to the `CalculixResults` task object
    - `eig`: Refers to the `AllEigen` task object
2. `Postprocess`:
3. `CodeAsterResults`:
    - `in_comm_file`: Path to the input comm file
    - `in_med_file`: Path to the input MED file
    - `out_rmed_file`: Path to the output RMED file
4. `CalculixResults`:
5.

The `tasks.objects.py` defines the various task objects which will have fields representing task parameters which can be referred to 
in the report

