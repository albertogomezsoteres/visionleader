;; UFV campus navigation - unified PDDL domain.
;; Action costs are seconds of user effort. Elevator/stairs presence is
;; declared per-building in the problem file.

(define (domain campus-navigation)
  (:requirements :strips :typing :action-costs)

  (:types person location - object)

  (:functions
    (total-cost) - number
    (distance ?u1 - location ?u2 - location) - number
    (distance_outdoor ?u1 - location ?u2 - location) - number
  )

  (:predicates
    (at ?p - person ?u - location)

    (hallway_connected     ?u1 ?u2 - location)
    (elevator_connected    ?u1 ?u2 - location)
    (stairs_up_connected   ?u1 ?u2 - location)
    (stairs_down_connected ?u1 ?u2 - location)
    (outdoor_connected     ?u1 ?u2 - location)

    (is_elevator ?u - location)
    (is_stairs   ?u - location)

    (elevator_verified ?u - location)
    (stairs_verified   ?u - location)

    (open ?u - location)

    (hurry_mode)
  )

  (:action walk
    :parameters (?p - person ?u1 - location ?u2 - location)
    :precondition (and (at ?p ?u1) (hallway_connected ?u1 ?u2) (open ?u2))
    :effect (and (not (at ?p ?u1)) (at ?p ?u2)
                 (increase (total-cost) (distance ?u1 ?u2)))
  )

  (:action verify_elevator
    :parameters (?p - person ?u - location)
    :precondition (and (at ?p ?u) (is_elevator ?u) (open ?u))
    :effect (and (elevator_verified ?u) (increase (total-cost) 5))
  )

  (:action use_elevator
    :parameters (?p - person ?u1 - location ?u2 - location)
    :precondition (and (at ?p ?u1) (is_elevator ?u1) (elevator_verified ?u1)
                       (elevator_connected ?u1 ?u2))
    :effect (and (not (at ?p ?u1)) (at ?p ?u2)
                 (not (elevator_verified ?u1))
                 (increase (total-cost) 15))
  )

  (:action validate_stairs
    :parameters (?p - person ?u - location)
    :precondition (and (at ?p ?u) (is_stairs ?u) (open ?u))
    :effect (and (stairs_verified ?u) (increase (total-cost) 5))
  )

  (:action climb_stairs_accessible
    :parameters (?p - person ?u1 - location ?u2 - location)
    :precondition (and (at ?p ?u1) (is_stairs ?u1) (stairs_verified ?u1)
                       (stairs_up_connected ?u1 ?u2) (not (hurry_mode)))
    :effect (and (not (at ?p ?u1)) (at ?p ?u2)
                 (not (stairs_verified ?u1))
                 (increase (total-cost) 30))
  )

  (:action descend_stairs_accessible
    :parameters (?p - person ?u1 - location ?u2 - location)
    :precondition (and (at ?p ?u1) (is_stairs ?u1) (stairs_verified ?u1)
                       (stairs_down_connected ?u1 ?u2) (not (hurry_mode)))
    :effect (and (not (at ?p ?u1)) (at ?p ?u2)
                 (not (stairs_verified ?u1))
                 (increase (total-cost) 25))
  )

  (:action climb_stairs_fast
    :parameters (?p - person ?u1 - location ?u2 - location)
    :precondition (and (at ?p ?u1) (is_stairs ?u1) (stairs_verified ?u1)
                       (stairs_up_connected ?u1 ?u2) (hurry_mode))
    :effect (and (not (at ?p ?u1)) (at ?p ?u2)
                 (not (stairs_verified ?u1))
                 (increase (total-cost) 12))
  )

  (:action descend_stairs_fast
    :parameters (?p - person ?u1 - location ?u2 - location)
    :precondition (and (at ?p ?u1) (is_stairs ?u1) (stairs_verified ?u1)
                       (stairs_down_connected ?u1 ?u2) (hurry_mode))
    :effect (and (not (at ?p ?u1)) (at ?p ?u2)
                 (not (stairs_verified ?u1))
                 (increase (total-cost) 8))
  )

  (:action outdoor_walk
    :parameters (?p - person ?u1 - location ?u2 - location)
    :precondition (and (at ?p ?u1) (outdoor_connected ?u1 ?u2) (open ?u2))
    :effect (and (not (at ?p ?u1)) (at ?p ?u2)
                 (increase (total-cost) (distance_outdoor ?u1 ?u2)))
  )
)
