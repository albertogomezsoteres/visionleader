;; Building G navigation domain: DISTANCE-AWARE room-level symbolic layer.
;;
;; This domain is loaded only when the user is navigating inside Building G
;; (Escuela Politécnica Superior). The planner reasons over individual
;; locations (ubicaciones) AND their metric distances, so plans minimise
;; actual meters walked — not just number of hops.
;;
;; The topology (which rooms connect to which) and the metric distances
;; both live in the PROBLEM file, not here. This domain only defines the
;; predicates, the (distancia ?u1 ?u2) numeric function and the actions.
;; The problem file's :init section encodes:
;;   * (conectado_pasillo u1 u2)           ; existence of an edge
;;   * (= (distancia u1 u2) N)             ; metric cost of that edge
;;
;; Cost model (meters / meter-equivalent effort). Every number below has
;; a physical interpretation: "how many seconds of walking at ~1 m/s this
;; action costs in terms of effort / time". This makes every cost
;; defensible ("5 seconds to take the elevator photo", etc.) instead of
;; tuned-until-it-works.
;;
;;   caminar               : variable — equal to the edge distance
;;   verificar_ascensor    : 5    (5s photo + PaliGemma confirmation)
;;   usar_ascensor         : 15   (doors + ride + exit, per use)
;;   validar_escaleras     : 10   (10s photo + handrail/direction check)
;;   subir_escaleras       : 30   (slow climb with handrail, per floor)
;;   bajar_escaleras       : 25   (slow descent with handrail, per floor)
;;   subir_escaleras_rapido: 12   (fast climb, no verification, per floor)
;;   bajar_escaleras_rapido: 8    (fast descent, no verification, per floor)
;;
;; Totals per floor change:
;;
;;   Accessible elevator up/down   : 5 + 15 = 20
;;   Accessible stairs up          : 10 + 30 = 40
;;   Accessible stairs down        : 10 + 25 = 35
;;   Hurry elevator up/down        : 5 + 15 = 20
;;   Hurry stairs up               : 12
;;   Hurry stairs down             : 8
;;
;; Balance summary:
;;   * Accessible mode: elevator (20) clearly beats stairs (35-40).
;;   * Hurry mode, 1 floor: stairs (8-12) beat elevator (20).
;;   * Hurry mode, 2 floors: stairs (16-24) still compete with elevator (20).
;;     Small margin — real decision depends on walk-to-node distances.

(define (domain building-g)
  (:requirements :strips :typing :action-costs)

  (:types
    robot ubicacion planta - object
  )

  (:functions
    (total-cost) - number
    ;; Metric distance in meters between two directly connected rooms.
    ;; Set once in :init, never changes. Fast Downward grounds caminar
    ;; with the right numeric cost at problem-instantiation time.
    (distancia ?u1 - ubicacion ?u2 - ubicacion) - number
  )

  (:predicates
    ;; Robot's current location (one specific room / POI)
    (en ?r - robot ?u - ubicacion)

    ;; Which floor a location is on (set once in the problem init)
    (en_planta ?u - ubicacion ?p - planta)

    ;; Directed hallway connection between two rooms on the same floor.
    ;; Used by the (caminar ...) action. The problem file encodes the
    ;; full Building G topology with these facts.
    (conectado_pasillo ?u1 - ubicacion ?u2 - ubicacion)

    ;; Vertical elevator connection between two elevator nodes on
    ;; different floors (e.g. ascensor_p0 <-> ascensor_p1)
    (conectado_ascensor ?u1 - ubicacion ?u2 - ubicacion)

    ;; Directed stair connections (one per direction)
    (conectado_escalera_subir ?u1 - ubicacion ?u2 - ubicacion)
    (conectado_escalera_bajar ?u1 - ubicacion ?u2 - ubicacion)

    ;; Tags identifying which locations are elevators / stairs (so the
    ;; verificar/validar actions can only run at those locations).
    (es_ascensor ?u - ubicacion)
    (es_escalera ?u - ubicacion)

    ;; Elevator safety state machine (camera-verified via the VLM)
    (ascensor_disponible ?u - ubicacion)

    ;; Stairs safety state machine (accessible mode only)
    (escaleras_verificadas ?u - ubicacion)

    ;; Dynamic availability: a room is (abierto) when it can be entered
    ;; right now. Closed classrooms, broken elevators, stairs closed for
    ;; maintenance, etc. simply do NOT receive the (abierto) fact in the
    ;; problem init — the caminar / verificar_ascensor / validar_escaleras
    ;; preconditions then make every action that touches them inapplicable.
    (abierto ?u - ubicacion)

    ;; User preference flag: prefer stairs over elevator
    (modo_rapido)
  )

  ;; Walking one hop along a hallway edge. The cost is the edge's
  ;; metric distance, so plans minimise total meters walked.

  (:action caminar
    :parameters (?r - robot ?u1 - ubicacion ?u2 - ubicacion)
    :precondition (and
      (en ?r ?u1)
      (conectado_pasillo ?u1 ?u2)
      (abierto ?u2)                       ; target room must be available
    )
    :effect (and
      (not (en ?r ?u1))
      (en ?r ?u2)
      (increase (total-cost) (distancia ?u1 ?u2))
    )
  )

  ;; Elevator path (2 actions, total cost 10)

  (:action verificar_ascensor
    :parameters (?r - robot ?u - ubicacion)
    :precondition (and
      (en ?r ?u)
      (es_ascensor ?u)
      (abierto ?u)                        ; elevator must be in service
    )
    :effect (and
      (ascensor_disponible ?u)
      (increase (total-cost) 5)
    )
  )

  (:action usar_ascensor
    :parameters (?r - robot ?u1 - ubicacion ?u2 - ubicacion)
    :precondition (and
      (en ?r ?u1)
      (es_ascensor ?u1)
      (ascensor_disponible ?u1)
      (conectado_ascensor ?u1 ?u2)
    )
    :effect (and
      (not (en ?r ?u1))
      (en ?r ?u2)
      (not (ascensor_disponible ?u1))
      (increase (total-cost) 15)
    )
  )

  ;; Stairs path, accessible mode (2 actions, total cost 40 up / 35 down)

  (:action validar_escaleras
    :parameters (?r - robot ?u - ubicacion)
    :precondition (and
      (en ?r ?u)
      (es_escalera ?u)
      (abierto ?u)                        ; stairs must be in service
      (not (modo_rapido))
    )
    :effect (and
      (escaleras_verificadas ?u)
      (increase (total-cost) 10)
    )
  )

  (:action subir_escaleras
    :parameters (?r - robot ?u1 - ubicacion ?u2 - ubicacion)
    :precondition (and
      (en ?r ?u1)
      (es_escalera ?u1)
      (escaleras_verificadas ?u1)
      (conectado_escalera_subir ?u1 ?u2)
    )
    :effect (and
      (not (en ?r ?u1))
      (en ?r ?u2)
      (not (escaleras_verificadas ?u1))
      (increase (total-cost) 30)
    )
  )

  (:action bajar_escaleras
    :parameters (?r - robot ?u1 - ubicacion ?u2 - ubicacion)
    :precondition (and
      (en ?r ?u1)
      (es_escalera ?u1)
      (escaleras_verificadas ?u1)
      (conectado_escalera_bajar ?u1 ?u2)
    )
    :effect (and
      (not (en ?r ?u1))
      (en ?r ?u2)
      (not (escaleras_verificadas ?u1))
      (increase (total-cost) 25)
    )
  )

  ;; Stairs path, hurry mode (1 action, no safety check)

  (:action subir_escaleras_rapido
    :parameters (?r - robot ?u1 - ubicacion ?u2 - ubicacion)
    :precondition (and
      (en ?r ?u1)
      (es_escalera ?u1)
      (modo_rapido)
      (conectado_escalera_subir ?u1 ?u2)
    )
    :effect (and
      (not (en ?r ?u1))
      (en ?r ?u2)
      (increase (total-cost) 12)
    )
  )

  (:action bajar_escaleras_rapido
    :parameters (?r - robot ?u1 - ubicacion ?u2 - ubicacion)
    :precondition (and
      (en ?r ?u1)
      (es_escalera ?u1)
      (modo_rapido)
      (conectado_escalera_bajar ?u1 ?u2)
    )
    :effect (and
      (not (en ?r ?u1))
      (en ?r ?u2)
      (increase (total-cost) 8)
    )
  )
)
