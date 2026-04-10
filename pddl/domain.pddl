;; Campus navigation domain — symbolic layer (building + floor only)
;;
;; State abstraction: the planner reasons about (edificio, planta), not individual
;; classrooms. Fine-grained walking text ("turn left", corridor detail) lives in
;; campus_graph.json under local_connections and is merged by the conversation agent
;; after each PDDL action is interpreted.
;;
;; Intended users: people with low vision using voice + photo assistance; elevator
;; and stairs are validated autonomously with camera guidance before movement.
;;
;; Two navigation profiles controlled by the (modo_rapido) predicate:
;;
;;   Accessible (default)          Hurry (modo_rapido)
;;   ─────────────────────         ────────────────────
;;   Elevator total cost: 3        Elevator total cost: 3
;;   Stairs-up total cost: 6       Stairs-up total cost: 2
;;   Stairs-down total cost: 5     Stairs-down total cost: 1
;;   Outdoor walk cost: 5          Outdoor walk cost: 5
;;
;; In accessible mode the planner picks the elevator because it is
;; cheaper.  In hurry mode the planner picks stairs because the
;; safety-check steps are skipped and the cost drops below the elevator.

(define (domain campus-navigation)
  (:requirements :strips :typing :action-costs)

  (:types
    robot edificio planta tipo_conexion - object
  )

  (:functions
    (total-cost) - number
  )

  (:predicates
    ;; Where the robot (user) is right now
    (en ?r - robot ?b - edificio ?p - planta)

    ;; Facilities available at a given building + floor
    (hay_ascensor ?b - edificio ?p - planta)
    (hay_escalera ?b - edificio ?p - planta)
    (hay_cafeteria ?b - edificio ?p - planta)
    (hay_gimnasio ?b - edificio ?p - planta)

    ;; Directed edge between two building-floor pairs via a connection type
    (conectado ?b1 - edificio ?p1 - planta
              ?b2 - edificio ?p2 - planta
              ?t  - tipo_conexion)

    ;; Connection-type tags (set once in init, never change)
    (es_ascensor        ?t - tipo_conexion)
    (es_escalera_subir  ?t - tipo_conexion)
    (es_escalera_bajar  ?t - tipo_conexion)
    (es_pasillo         ?t - tipo_conexion)

    ;; Elevator readiness (validated through app guidance + VLM)
    (ascensor_disponible ?b - edificio ?p - planta)

    ;; Stair safety state machine (accessible mode only)
    (escaleras_verificadas ?b - edificio ?p - planta)

    ;; User preference flag
    (modo_rapido)
  )

  ;; ═══════════════════════════════════════════════════════════════════════
  ;; Outdoor movement between buildings on the same floor
  ;; ═══════════════════════════════════════════════════════════════════════

  (:action mover_edificio
    :parameters (?r - robot
                 ?bo - edificio ?bd - edificio
                 ?p - planta
                 ?t - tipo_conexion)
    :precondition (and
      (en ?r ?bo ?p)
      (conectado ?bo ?p ?bd ?p ?t)
      (es_pasillo ?t)
    )
    :effect (and
      (not (en ?r ?bo ?p))
      (en ?r ?bd ?p)
      (increase (total-cost) 5)
    )
  )

  ;; ═══════════════════════════════════════════════════════════════════════
  ;; Elevator path (2 actions, total cost 3)
  ;; ═══════════════════════════════════════════════════════════════════════

  (:action verificar_ascensor
    :parameters (?r - robot ?b - edificio ?p - planta)
    :precondition (and
      (en ?r ?b ?p)
      (hay_ascensor ?b ?p)
    )
    :effect (and
      (ascensor_disponible ?b ?p)
      (increase (total-cost) 1)
    )
  )

  (:action usar_ascensor
    :parameters (?r - robot
                 ?b - edificio
                 ?po - planta ?pd - planta
                 ?t - tipo_conexion)
    :precondition (and
      (en ?r ?b ?po)
      (hay_ascensor ?b ?po)
      (ascensor_disponible ?b ?po)
      (conectado ?b ?po ?b ?pd ?t)
      (es_ascensor ?t)
    )
    :effect (and
      (not (en ?r ?b ?po))
      (en ?r ?b ?pd)
      (not (ascensor_disponible ?b ?po))
      (increase (total-cost) 2)
    )
  )

  ;; ═══════════════════════════════════════════════════════════════════════
  ;; Stairs path  accessible mode (2 actions, total cost 6 up / 5 down)
  ;; ═══════════════════════════════════════════════════════════════════════

  (:action validar_escaleras
    :parameters (?r - robot ?b - edificio ?p - planta)
    :precondition (and
      (en ?r ?b ?p)
      (hay_escalera ?b ?p)
      (not (modo_rapido))
    )
    :effect (and
      (escaleras_verificadas ?b ?p)
      (increase (total-cost) 3)
    )
  )

  (:action subir_escaleras
    :parameters (?r - robot
                 ?b - edificio
                 ?po - planta ?pd - planta
                 ?t - tipo_conexion)
    :precondition (and
      (en ?r ?b ?po)
      (hay_escalera ?b ?po)
      (escaleras_verificadas ?b ?po)
      (conectado ?b ?po ?b ?pd ?t)
      (es_escalera_subir ?t)
    )
    :effect (and
      (not (en ?r ?b ?po))
      (en ?r ?b ?pd)
      (not (escaleras_verificadas ?b ?po))
      (increase (total-cost) 3)
    )
  )

  (:action bajar_escaleras
    :parameters (?r - robot
                 ?b - edificio
                 ?po - planta ?pd - planta
                 ?t - tipo_conexion)
    :precondition (and
      (en ?r ?b ?po)
      (hay_escalera ?b ?po)
      (escaleras_verificadas ?b ?po)
      (conectado ?b ?po ?b ?pd ?t)
      (es_escalera_bajar ?t)
    )
    :effect (and
      (not (en ?r ?b ?po))
      (en ?r ?b ?pd)
      (not (escaleras_verificadas ?b ?po))
      (increase (total-cost) 2)
    )
  )

  ;; ═══════════════════════════════════════════════════════════════════════
  ;; Stairs path  hurry mode (1 action, total cost 2 up / 1 down)
  ;; Safety checks are skipped when the user is in a rush.
  ;; ═══════════════════════════════════════════════════════════════════════

  (:action subir_escaleras_rapido
    :parameters (?r - robot
                 ?b - edificio
                 ?po - planta ?pd - planta
                 ?t - tipo_conexion)
    :precondition (and
      (en ?r ?b ?po)
      (hay_escalera ?b ?po)
      (modo_rapido)
      (conectado ?b ?po ?b ?pd ?t)
      (es_escalera_subir ?t)
    )
    :effect (and
      (not (en ?r ?b ?po))
      (en ?r ?b ?pd)
      (increase (total-cost) 2)
    )
  )

  (:action bajar_escaleras_rapido
    :parameters (?r - robot
                 ?b - edificio
                 ?po - planta ?pd - planta
                 ?t - tipo_conexion)
    :precondition (and
      (en ?r ?b ?po)
      (hay_escalera ?b ?po)
      (modo_rapido)
      (conectado ?b ?po ?b ?pd ?t)
      (es_escalera_bajar ?t)
    )
    :effect (and
      (not (en ?r ?b ?po))
      (en ?r ?b ?pd)
      (increase (total-cost) 1)
    )
  )
)
