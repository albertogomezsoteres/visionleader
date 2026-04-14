;; Outdoor inter-building navigation domain (building + floor level).
;; Used when the user must cross campus between different buildings.
;; Intra-building navigation uses domain_indoor.pddl (all 14 buildings).
;;
;; Cost model (accessible / hurry):
;;   outdoor walk: 5     elevator: 1+2=3     stairs up: 3+3=6 / 2
;;   stairs down: 3+2=5 / 1

(define (domain campus-outdoor)
  (:requirements :strips :typing :action-costs)

  (:types
    robot edificio planta tipo_conexion - object
  )

  (:functions (total-cost) - number)

  (:predicates
    (en ?r - robot ?b - edificio ?p - planta)

    (hay_ascensor ?b - edificio ?p - planta)
    (hay_escalera ?b - edificio ?p - planta)

    (conectado ?b1 - edificio ?p1 - planta
               ?b2 - edificio ?p2 - planta
               ?t  - tipo_conexion)

    (es_ascensor       ?t - tipo_conexion)
    (es_escalera_subir ?t - tipo_conexion)
    (es_escalera_bajar ?t - tipo_conexion)
    (es_pasillo        ?t - tipo_conexion)

    (ascensor_disponible   ?b - edificio ?p - planta)
    (escaleras_verificadas ?b - edificio ?p - planta)

    (modo_rapido)
  )

  (:action mover_edificio
    :parameters (?r - robot ?bo - edificio ?bd - edificio ?p - planta ?t - tipo_conexion)
    :precondition (and (en ?r ?bo ?p) (conectado ?bo ?p ?bd ?p ?t) (es_pasillo ?t))
    :effect (and (not (en ?r ?bo ?p)) (en ?r ?bd ?p) (increase (total-cost) 5))
  )

  (:action verificar_ascensor
    :parameters (?r - robot ?b - edificio ?p - planta)
    :precondition (and (en ?r ?b ?p) (hay_ascensor ?b ?p))
    :effect (and (ascensor_disponible ?b ?p) (increase (total-cost) 1))
  )

  (:action usar_ascensor
    :parameters (?r - robot ?b - edificio ?po - planta ?pd - planta ?t - tipo_conexion)
    :precondition (and
      (en ?r ?b ?po) (hay_ascensor ?b ?po) (ascensor_disponible ?b ?po)
      (conectado ?b ?po ?b ?pd ?t) (es_ascensor ?t))
    :effect (and
      (not (en ?r ?b ?po)) (en ?r ?b ?pd)
      (not (ascensor_disponible ?b ?po)) (increase (total-cost) 2))
  )

  (:action validar_escaleras
    :parameters (?r - robot ?b - edificio ?p - planta)
    :precondition (and (en ?r ?b ?p) (hay_escalera ?b ?p) (not (modo_rapido)))
    :effect (and (escaleras_verificadas ?b ?p) (increase (total-cost) 3))
  )

  (:action subir_escaleras
    :parameters (?r - robot ?b - edificio ?po - planta ?pd - planta ?t - tipo_conexion)
    :precondition (and
      (en ?r ?b ?po) (hay_escalera ?b ?po) (escaleras_verificadas ?b ?po)
      (conectado ?b ?po ?b ?pd ?t) (es_escalera_subir ?t))
    :effect (and
      (not (en ?r ?b ?po)) (en ?r ?b ?pd)
      (not (escaleras_verificadas ?b ?po)) (increase (total-cost) 3))
  )

  (:action bajar_escaleras
    :parameters (?r - robot ?b - edificio ?po - planta ?pd - planta ?t - tipo_conexion)
    :precondition (and
      (en ?r ?b ?po) (hay_escalera ?b ?po) (escaleras_verificadas ?b ?po)
      (conectado ?b ?po ?b ?pd ?t) (es_escalera_bajar ?t))
    :effect (and
      (not (en ?r ?b ?po)) (en ?r ?b ?pd)
      (not (escaleras_verificadas ?b ?po)) (increase (total-cost) 2))
  )

  (:action subir_escaleras_rapido
    :parameters (?r - robot ?b - edificio ?po - planta ?pd - planta ?t - tipo_conexion)
    :precondition (and
      (en ?r ?b ?po) (hay_escalera ?b ?po) (modo_rapido)
      (conectado ?b ?po ?b ?pd ?t) (es_escalera_subir ?t))
    :effect (and (not (en ?r ?b ?po)) (en ?r ?b ?pd) (increase (total-cost) 2))
  )

  (:action bajar_escaleras_rapido
    :parameters (?r - robot ?b - edificio ?po - planta ?pd - planta ?t - tipo_conexion)
    :precondition (and
      (en ?r ?b ?po) (hay_escalera ?b ?po) (modo_rapido)
      (conectado ?b ?po ?b ?pd ?t) (es_escalera_bajar ?t))
    :effect (and (not (en ?r ?b ?po)) (en ?r ?b ?pd) (increase (total-cost) 1))
  )
)
