allprojects {
    repositories {
        google()
        mavenCentral()
    }
}

// ESTA ES LA PIEZA QUE FALTA:
// Le dice a todos los módulos que usen la carpeta /build de la raíz del proyecto
rootProject.layout.buildDirectory.set(file("${project.projectDir}/../build"))

subprojects {
    val newSubprojectBuildDir = rootProject.layout.buildDirectory.dir(project.name)
    project.layout.buildDirectory.set(newSubprojectBuildDir)
}

subprojects {
    project.evaluationDependsOn(":app")
}

tasks.register<Delete>("clean") {
    delete(rootProject.layout.buildDirectory)
}