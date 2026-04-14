;; Building CD (Centro Deportivo) navigation domain.
;;
;; For the TFG demo, CD only has two floors (cafeteria on floor 0, gym on
;; floor -1) and is not developed at room level — the planner only needs
;; to decide between elevator and stairs, which is exactly the same
;; structure as the current global domain.
;;
;; This file exists so that the hierarchical planner can load a
;; CD-specific domain instead of the global one when the user is already
;; inside Building CD. Cross-building navigation still uses domain.pddl.

(define (domain building-cd)
  (:requirements :strips :typing :action-costs)

  (:types
    robot ubicacion planta - object
  )

  (:functions
    (total-cost) - number
  )

  (:predicates
    (en ?r - robot ?u - ubicacion)
    (en_planta ?u - ubicacion ?p - planta)

    (conectado_pasillo ?u1 - ubicacion ?u2 - ubicacion)
    (conectado_ascensor ?u1 - ubicacion ?u2 - ubicacion)
    (conectado_escalera_subir ?u1 - ubicacion ?u2 - ubicacion)
    (conectado_escalera_bajar ?u1 - ubicacion ?u2 - ubicacion)

    (es_ascensor ?u - ubicacion)
    (es_escalera ?u - ubicacion)
    (es_cafeteria ?u - ubicacion)
    (es_gimnasio ?u - ubicacion)

    (ascensor_disponible ?u - ubicacion)
    (escaleras_verificadas ?u - ubicacion)

    ;; Dynamic availability (see domain_G.pddl for rationale)
    (abierto ?u - ubicacion)

    (modo_rapido)
  )

  (:action caminar
    :parameters (?r - robot ?u1 - ubicacion ?u2 - ubicacion)
    :precondition (and
      (en ?r ?u1)
      (conectado_pasillo ?u1 ?u2)
      (abierto ?u2)
    )
    :effect (and
      (not (en ?r ?u1))
      (en ?r ?u2)
      (increase (total-cost) 1)
    )
  )

  (:action verificar_ascensor
    :parameters (?r - robot ?u - ubicacion)
    :precondition (and (en ?r ?u) (es_ascensor ?u) (abierto ?u))
    :effect (and (ascensor_disponible ?u) (increase (total-cost) 1))
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
      (increase (total-cost) 2)
    )
  )

  (:action validar_escaleras
    :parameters (?r - robot ?u - ubicacion)
    :precondition (and (en ?r ?u) (es_escalera ?u) (abierto ?u) (not (modo_rapido)))
    :effect (and (escaleras_verificadas ?u) (increase (total-cost) 3))
  )

  (:action subir_escaleras
    :parameters (?r - robot ?u1 - ubicacion ?u2 - ubicacion)
    :precondition (and
      (en ?r ?u1) (es_escalera ?u1) (escaleras_verificadas ?u1)
      (conectado_escalera_subir ?u1 ?u2)
    )
    :effect (and
      (not (en ?r ?u1)) (en ?r ?u2)
      (not (escaleras_verificadas ?u1))
      (increase (total-cost) 3)
    )
  )

  (:action bajar_escaleras
    :parameters (?r - robot ?u1 - ubicacion ?u2 - ubicacion)
    :precondition (and
      (en ?r ?u1) (es_escalera ?u1) (escaleras_verificadas ?u1)
      (conectado_escalera_bajar ?u1 ?u2)
    )
    :effect (and
      (not (en ?r ?u1)) (en ?r ?u2)
      (not (escaleras_verificadas ?u1))
      (increase (total-cost) 2)
    )
  )

  (:action subir_escaleras_rapido
    :parameters (?r - robot ?u1 - ubicacion ?u2 - ubicacion)
    :precondition (and
      (en ?r ?u1) (es_escalera ?u1) (modo_rapido)
      (conectado_escalera_subir ?u1 ?u2)
    )
    :effect (and
      (not (en ?r ?u1)) (en ?r ?u2)
      (increase (total-cost) 2)
    )
  )

  (:action bajar_escaleras_rapido
    :parameters (?r - robot ?u1 - ubicacion ?u2 - ubicacion)
    :precondition (and
      (en ?r ?u1) (es_escalera ?u1) (modo_rapido)
      (conectado_escalera_bajar ?u1 ?u2)
    )
    :effect (and
      (not (en ?r ?u1)) (en ?r ?u2)
      (increase (total-cost) 1)
    )
  )
)
