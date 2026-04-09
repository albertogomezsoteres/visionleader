allprojects {
    repositories {
        google()
        mavenCentral()
    }
}

// Build output lives OUTSIDE OneDrive to avoid file-lock / sync errors.
val externalBuild = file("C:/tmp/tfg-build")
rootProject.layout.buildDirectory.set(externalBuild)

subprojects {
    project.layout.buildDirectory.set(externalBuild.resolve(project.name))
}
subprojects {
    project.evaluationDependsOn(":app")
}

tasks.register<Delete>("clean") {
    delete(rootProject.layout.buildDirectory)
}
